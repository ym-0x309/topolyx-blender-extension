# Topolyx Import/Export

[English(`en_US`)](/README.md) | [한국어(`ko_KR`)](/README_ko_KR.md)

![Topolyx Import/Export](/images/topolyx-wordmark-1280-640.png)

블렌더 메쉬 데이터를 Topolyx 포맷(`.tlyx`)으로 익스포트하고 임포트하는 블렌더 익스텐션입니다.
포맷에 대한 자세한 정보는 [해당 레포지토리](https://github.com/ym-0x309/topolyx)를 참고하십시오.

- Topolyx 포맷 버전: `v1.0.0` 이상
- 지원 Blender 버전: `5.1.0` 이상

## 주요 기능

- Vertex / Edge / Face / Face Corner topology 보존
- `POINT`, `EDGE`, `FACE`, `CORNER` domain attribute 익스포트/임포트
- Object transform 및 `meters_per_unit` 스케일 처리
- 동일 mesh data block 공유
- Topolyx 1.0.0 고정 좌표계(`+Z` up, `+Y` forward, right-handed, CCW) 사용

## 설치

아직 [extensions.blender.org](https://extensions.blender.org)에 등록되지 않았기 때문에, 수동 설치해야 합니다.

1. [최신 릴리즈](https://github.com/ym-0x309/topolyx_import_export/releases) 다운로드
2. edit > preferences > get extensions > install from disk

## 사용

- 익스포트: `File > Export > Topolyx (.tlyx)`
- 임포트: `File > Import > Topolyx (.tlyx)`

## 버그 제보

[Issues](https://github.com/ym-0x309/topolyx_import_export/issues) 페이지에서 제보하세요.