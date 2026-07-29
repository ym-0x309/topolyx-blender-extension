# Topolyx Import/Export

Blender mesh 데이터를 Topolyx 1.0.0 포맷(`.tlyx`)으로 익스포트하고 임포트하는 Blender Extension(add-on)입니다.

- Topolyx 포맷 버전: `v1.0.0`
- 지원 Blender 버전: `5.1.0` 이상
- 파일은 단일 `.tlyx` 파일(JSON + BIN 청크 통합)입니다.

## 주요 기능

- Vertex / Edge / Face / Face Corner topology 보존
- `POINT`, `EDGE`, `FACE`, `CORNER` domain attribute 익스포트/임포트
- Object transform 및 `meters_per_unit` 스케일 처리
- 동일 mesh data block 공유
- Topolyx 1.0.0 고정 좌표계(`+Z` up, `+Y` forward, right-handed, CCW) 사용

## 설치

`blender_manifest.toml`이 들어있는 디렉터리를 Blender Extension 시스템을 통해 설치하고 활성화합니다.

## 사용

- 익스포트: `File > Export > Topolyx (.tlyx)`
- 임포트: `File > Import > Topolyx (.tlyx)`

## 테스트

Blender 5.1 이상에서 아래 명령으로 실행합니다.

```bash
blender -b -P tests/run_all.py
```

자세한 내용은 [docs/TESTING.md](docs/TESTING.md)를 참고하세요.

## 라이선스

GPL 3.0 License
