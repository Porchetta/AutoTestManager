# Frontend Local Run

WSL 터미널에서 프론트를 직접 실행할 때 사용하는 명령 정리입니다.

## 1. frontend 디렉터리로 이동

```bash
cd /home/hyun/develope/AutoTestManager/frontend
```

## 2. 환경 파일 준비

최초 1회만 실행하면 됩니다.

```bash
cp .env.example .env
```

기본값:

```env
VITE_API_BASE_URL=http://127.0.0.1:10223
```

## 3. 의존성 설치

최초 1회 또는 `package.json` 변경 후 실행합니다.

```bash
npm install
```

## 4. 개발 서버 실행

```bash
npm run dev
```

## 5. 접속 주소

- Frontend: `http://127.0.0.1:4203`
- Backend API: `http://127.0.0.1:10223`

## 6. 종료

실행 중인 터미널에서:

```bash
Ctrl + C
```

## 7. 빌드 확인

```bash
npm run build
```
