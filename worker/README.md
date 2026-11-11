# SAFE-DD 서버 도구 (Cloudflare Worker)

GitHub Pages 웹앱이 부르는 선택 서버. 없어도 웹앱은 저장된 실행 재생·SEC 제출목록 조회가 된다.
`lookup`(티커→CIK) · `filings`(공시 목록) · `analyze`(본문 분류·4변수 인용·원문 일치 점검). 키 불필요, 무료 플랜 하루 10만 요청.

배포: `cd worker && npx wrangler deploy` → 나온 주소를 `docs/config.js`의 `API_BASE`에 넣는다. 현재 배포 주소: https://little-king-4660.best5218o.workers.dev (Cloudflare 계정 best5218o, 이름 little-king-4660 — 대시보드에서 이름 변경 불가였음).
