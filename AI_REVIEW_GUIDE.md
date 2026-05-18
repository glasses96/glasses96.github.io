# AI 글 리뷰 사용 방법

이 repo는 `_posts/*.md` 글을 Pull Request로 올리면 GitHub Actions가 AI 리뷰를 PR 코멘트로 남기도록 설정되어 있다.

## 최초 설정

GitHub repo에서 OpenAI API 키를 secret으로 등록해야 한다.

1. GitHub repo 접속
2. `Settings` 클릭
3. `Secrets and variables` 클릭
4. `Actions` 클릭
5. `New repository secret` 클릭
6. 이름에 `OPENAI_API_KEY` 입력
7. 값에 OpenAI API 키 입력
8. `Add secret` 클릭

기본 모델은 `gpt-5.5`다.

모델을 바꾸고 싶으면 `Settings > Secrets and variables > Actions > Variables`에 아래 값을 추가한다.

```text
OPENAI_MODEL
```

예시:

```text
gpt-5.5
```

## AI 리뷰 받는 글 업로드 방법

기존처럼 바로 `main` 브랜치에 push하면 AI 리뷰가 실행되지 않는다.

AI 리뷰를 받으려면 글마다 새 브랜치를 만들고 Pull Request를 열어야 한다.

```bash
git checkout main
git fetch origin --prune
git pull --ff-only origin main

git checkout -b post/new-post

git add --all
git commit -m "Add post"

git push -u origin post/new-post
```

push 후 GitHub에서 `Compare & pull request` 버튼을 눌러 Pull Request를 만든다.

Pull Request가 만들어지면 GitHub Actions가 변경된 `_posts/*.md` 파일을 읽고 PR 코멘트로 AI 리뷰를 남긴다.

## 리뷰 반영 후 다시 올리기

AI 리뷰를 보고 글을 수정한 뒤 같은 브랜치에서 다시 커밋하고 push한다.

```bash
git add --all
git commit -m "Update post"
git push
```

그러면 같은 Pull Request의 AI 리뷰 코멘트가 새 내용으로 업데이트된다.

## 블로그에 최종 발행하기

리뷰 반영이 끝나면 GitHub Pull Request 화면에서 `Merge pull request`를 누른다.

merge가 완료되면 기존 GitHub Pages 배포 workflow가 실행되고, 글이 블로그에 발행된다.

## PR merge 후 로컬 main 동기화

Pull Request를 merge하면 GitHub의 `main` 브랜치가 먼저 업데이트된다.

로컬 `main`은 자동으로 업데이트되지 않으므로, 다음 글 작업을 시작하기 전에 반드시 로컬 `main`을 최신 상태로 맞춘다.

```bash
git checkout main
git fetch origin --prune
git pull --ff-only origin main
```

그 다음 새 글 브랜치를 만든다.

```bash
git checkout -b post/new-post
```

이미 로컬에 남아 있는 작업 브랜치를 지우고 싶으면 cleanup 스크립트를 실행한다.

```powershell
cleanup_branches.ps1 -Apply
```

원격 브랜치는 GitHub에서 PR merge 후 자동 삭제되도록 설정할 수 있다.
GitHub repo의 `Settings > General`에서 아래로 스크롤한 뒤 `Pull Requests` 섹션의 `Automatically delete head branches`를 켠다.

해당 항목이 보이지 않으면 repo admin 권한이 있는지 확인한다.
GitHub CLI를 쓰는 경우 아래 명령으로도 설정할 수 있다.

```bash
gh api repos/glasses96/glasses96.github.io --method PATCH --field delete_branch_on_merge=true
```

## AI 리뷰 출력 형식

AI 리뷰는 아래 형식으로 생성된다.

```markdown
# 총평 요약

# 핵심 부분

# 틀림 및 보완 사항

# 추가 학습 필요 정보
```

## 주의사항

- `_posts/*.md` 파일이 변경된 Pull Request에서만 실행된다.
- OpenAI API 키가 등록되어 있지 않으면 workflow가 실패한다.
- 리뷰는 자동 검토이므로 최종 판단은 직접 확인해야 한다.
- 너무 긴 글은 앞부분 일부만 AI 리뷰 입력으로 사용될 수 있다.
