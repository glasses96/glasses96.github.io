import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from openai import OpenAI


COMMENT_MARKER = "<!-- ai-post-review -->"
MAX_POST_CHARS = int(os.getenv("AI_REVIEW_MAX_POST_CHARS", "60000"))

REVIEW_INSTRUCTIONS = """\
너는 기술 블로그 글을 리뷰하는 레드팀 전문 시니어 엔지니어다.
웹/시스템/클라우드/AD 보안, 취약점 분석, 익스플로잇 체인, 권한 상승, 탐지 회피와 방어 검증에 익숙한 전문가 관점으로 리뷰한다.
글쓴이가 공격 기법의 원리와 보안적 의미를 더 정확하게 정리하도록 돕는 것이 목표다.

규칙:
- 한국어로 작성한다.
- 과장하지 말고, 글에 실제로 있는 내용에 근거해 리뷰한다.
- 기술적으로 확실하지 않은 지적은 "확인 필요"라고 표시한다.
- 위험한 악용 절차를 새로 확장하기보다, 글에 이미 포함된 내용의 정확성, 원리, 전제 조건, 방어 관점을 중심으로 리뷰한다.
- 기술적으로 틀린 부분은 왜 틀렸는지 상세하게 설명한다.
- 특히 틀린 부분이 있다면, 검증 가능한 근거와 함께 수정 방향을 제시한다.
- 출력은 반드시 아래 4개 섹션만 사용한다.
- 각 섹션은 짧은 문단과 bullet을 섞어 읽기 쉽게 작성한다.

# 총평 요약
글의 목적, 전체 완성도, 독자가 얻을 수 있는 점을 요약한다.

# 핵심 부분
글에서 중요한 공격 흐름, 취약점 트리거 조건, 권한 경계 변화, 익스플로잇 성공 요인을 전문가 관점으로 정리한다.
기술적인 내용이 있다면 단순 요약에 그치지 말고 핵심 아이디어, 내부 원리, 왜 해당 기법이 통하는지, 어떤 환경 전제가 필요한지 설명한다.
가능하면 탐지/방어 관점에서 이 핵심 부분이 왜 중요한지도 짚는다.


# 틀림 및 보완 사항
기술적으로 틀렸거나 모호한 부분, 근거가 부족한 부분, 오해를 만들 수 있는 표현을 지적한다.
특히 기술적으로 틀린 부분은 상세하게 설명한다.
가능하면 수정 방향도 제시한다.

# 추가 학습 필요 정보
글쓴이가 더 공부하면 좋은 키워드, 공식 문서, 관련 개념을 제안한다.
"""


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def run_git_diff(base_sha: str, head_sha: str) -> list[str]:
    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=AMR",
            base_sha,
            head_sha,
            "--",
            "_posts",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip().startswith("_posts/") and line.strip().endswith(".md")
    ]


def read_post(path: str) -> str:
    text = Path(path).read_text(encoding="utf-8")
    if len(text) <= MAX_POST_CHARS:
        return text

    omitted = len(text) - MAX_POST_CHARS
    return (
        text[:MAX_POST_CHARS]
        + f"\n\n[NOTE] 글이 길어 이후 {omitted}자는 리뷰 입력에서 제외되었습니다.\n"
    )


def review_post(client: OpenAI, model: str, path: str, content: str) -> str:
    response = client.responses.create(
        model=model,
        instructions=REVIEW_INSTRUCTIONS,
        input=f"파일 경로: {path}\n\nMarkdown 글:\n\n{content}",
    )
    return response.output_text.strip()


def github_request(method: str, url: str, token: str, payload: dict | None = None):
    data = None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(request) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else None
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API request failed: {error.code} {detail}") from error


def upsert_pr_comment(repo: str, pr_number: str, token: str, body: str) -> None:
    base_url = f"https://api.github.com/repos/{repo}"
    comments_url = f"{base_url}/issues/{pr_number}/comments"
    comments = github_request("GET", comments_url, token)

    existing = next(
        (
            comment
            for comment in comments
            if comment.get("user", {}).get("type") == "Bot"
            and COMMENT_MARKER in comment.get("body", "")
        ),
        None,
    )

    payload = {"body": body}
    if existing:
        github_request("PATCH", existing["url"], token, payload)
    else:
        github_request("POST", comments_url, token, payload)


def build_comment(reviews: list[tuple[str, str]]) -> str:
    sections = [COMMENT_MARKER, "# AI 글 리뷰"]

    for path, review in reviews:
        sections.append(f"## `{path}`\n\n{review}")

    sections.append(
        "\n---\n"
        "이 코멘트는 `_posts/*.md` 변경 사항을 기준으로 GitHub Actions에서 자동 생성되었습니다."
    )
    return "\n\n".join(sections)


def main() -> int:
    openai_api_key = require_env("OPENAI_API_KEY")
    github_token = require_env("GITHUB_TOKEN")
    repo = require_env("GITHUB_REPOSITORY")
    pr_number = require_env("PR_NUMBER")
    base_sha = require_env("BASE_SHA")
    head_sha = require_env("HEAD_SHA")
    model = os.getenv("OPENAI_MODEL", "gpt-5.2")

    changed_posts = run_git_diff(base_sha, head_sha)
    if not changed_posts:
        print("No changed posts found.")
        return 0

    client = OpenAI(api_key=openai_api_key)
    reviews = []

    for path in changed_posts:
        print(f"Reviewing {path}")
        content = read_post(path)
        reviews.append((path, review_post(client, model, path, content)))

    upsert_pr_comment(repo, pr_number, github_token, build_comment(reviews))
    print(f"Reviewed {len(reviews)} post(s).")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"AI review failed: {exc}", file=sys.stderr)
        raise
