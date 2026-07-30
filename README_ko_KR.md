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

### 블렌더 익스텐션 기능으로 설치

> [!TIP]
> 해당 방법을 통해 설치하는 것을 권장합니다.

1. edit > preferences > get extensions
2. 검색창에서 `topolyx` 검색
3. `Topolyx Import/Export` 설치

### 디스크를 통해 설치

1. [최신 릴리즈](https://github.com/ym-0x309/topolyx_import_export/releases) 다운로드
2. edit > preferences > get extensions > install from disk

## 사용

> [!IMPORTANT]
> - 내보내기: `File > Export > Topolyx (.tlyx)`
> - 들여오기: `File > Import > Topolyx (.tlyx)`

### 내보내기

`File > Export > Topolyx (.tlyx)`

내보내기 옵션

- `Selection Only`: 활성화 시, 뷰포트에서 선택된 메쉬 오브젝트만 내보냅니다. 비활성화 시, 모든 메쉬 오브젝트를 내보냅니다.
- Coordinate System
  - `Meters per Unit`: 씬의 길이 1.0당 몇 미터인지를 나타냅니다. 기본값은 1.0입니다.
- Attribute Options
  - `Exclude Hidden/Internal Attributes`: 활성화 시, `.`으로 시작하는 숨겨져 있거나 블렌더 내부에서만 사용되는 attribute 및 topology 기본 정보에 저장되는 `position` attribute를 건너뜁니다. 비활성화 시, 모든 attribute를 저장합니다.
  - `Excluded Attributes`: attribute의 이름을 `,`로 분리해 입력하면, 해당 attribute들은 건너뜁니다.
  - `Remove Semantic Prefix`: 활성화 시, 아래의 `Auto Assign Semantics` 옵션의 활성화로 semantic이 감지되었을 때 해당 접두사를 제거합니다당(예: `DIRECTION_my_attr`라는 이름은 `my_attr`로 변경됩니다.). 비활성화 시, semantic이 감지되더라도 접두사가 제거되지 않습니다.
  - `Auto Assign Semantics`: 활성화 시, attribute 이름 앞의 `POSITION`, `DIRECTION`, `NORMAL`, `ROTATION`, `TANGENT`, `COLOR` 접두사를 인식하여, semantic을 자동 부여합니다(예: `DIRECTION_my_attr`라는 이름은 자동으로 `DIRECTION` semantic으로 배정됩니다.). 비활성화 시, topology 기본 정보에 저장되지 않는 attribute는 모두 `NONE`으로 배정됩니다.

### 들여오기

`File > Import > Topolyx (.tlyx)`

들여오기 옵션

- `Import Attributes`: 활성화 시, 파일의 topology 기본 정보 외의 attribute를 들여옵니다. 비활성화 시, topology 기본 정보만 들여옵니다.

## 버그 제보

[Issues](https://github.com/ym-0x309/topolyx_import_export/issues) 페이지에서 제보하세요.