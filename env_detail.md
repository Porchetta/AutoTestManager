기본 아키텍처

frontend/   Vue 3 + Vite + Pinia SPA
backend/    FastAPI + SQLAlchemy + SQLite API 서버
docs/       Front.md, Back.md, plan.md (구현 기준 문서)

구동 서버 : RedHat RHEL 7.9

이 프로젝트는 사내 폐쇄망 네트워크 환경에서 구동된다.
구동 서버 내에서는 docker compose가 불가능하므로, 개발 서버에서 필요한 모든 라이브러리를 포함해서 구동 환경을 docker image로 build 한 후 운영 환경에서 배포할 예정이다.

docker image 에는 source가 포함되지 않으며, 운영 서버에서는 docker image를 실행한 후 source file을 mount하여 사용할 예정이다.

이를 위해 필요한 사항들을 체크하고, docker build 후 운영 서버에서 docker run 할 수 있도록 구성요소를 점검하라.

운영 서버는 RedHat RHEL 7.9 이다.