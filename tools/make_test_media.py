"""송출 리허설용 '테스트 영상' 만들기 — 진짜 영상(Runway 등)이 나오기 전에 20분 흐름을 점검할 때 씁니다.

python tools/make_test_media.py            # 큐시트 길이 그대로 (카운트다운 60초 등)
python tools/make_test_media.py --short    # 모두 10초짜리 (빠른 점검용)

- 필요: ffmpeg  (Windows: winget install Gyan.FFmpeg → 터미널 다시 열기)
- 결과: app/static/media/ 에 countdown.mp4 · opening.mp4 · intro_1~3.mp4 · interview_1~3.mp4 ·
        profile_1~3.mp4 · closing.mp4 · anchor_loop.mp4 · bgm.mp3
- 이미 있는 파일은 건너뜀 (진짜 영상을 덮어쓰지 않음). 다시 만들려면 --force
- 화면에 '테스트 영상'이라고 크게 표시됨. 실제 방송에는 진짜 영상으로 바꿔 넣으세요.
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "app" / "static" / "media"
SHORT = "--short" in sys.argv
FORCE = "--force" in sys.argv

CANDS = {1: ("윤별하", "0xFF2BD6"), 2: ("류해온", "0x00E5FF"), 3: ("오로라", "0xA6FF00")}
# 파일 이름, 길이(초), 배경색, 큰 글자, 작은 글자
ITEMS = [("countdown.mp4", 60, "0x0B1120", "COUNTDOWN", "개표 카운트다운"),
         ("opening.mp4", 30, "0x141C2F", "오프닝", "AI 앵커 오프닝 멘트 (립싱크 아바타 자리)"),
         ("closing.mp4", 10, "0x141C2F", "마무리", "개표방송을 마칩니다")]
for cid, (name, color) in CANDS.items():
    ITEMS += [(f"intro_{cid}.mp4", 60, color, f"기호 {cid} {name}", "후보 소개 영상"),
              (f"interview_{cid}.mp4", 60, color, f"{name} 당선자", "당선자 인터뷰 영상"),
              (f"profile_{cid}.mp4", 60, color, f"{name}", "지난 이력·공약 영상")]

FONTS = ["C:/Windows/Fonts/malgunbd.ttf", "C:/Windows/Fonts/malgun.ttf",
         "/System/Library/Fonts/AppleSDGothicNeo.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
         "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"]


def font() -> str:
    for f in FONTS:
        if Path(f).exists():
            return f.replace(":", "\\:")      # ffmpeg 필터 안에서는 C: 의 : 를 \: 로
    sys.exit("한글 글꼴을 찾지 못했습니다. FONTS 목록에 글꼴 파일 경로를 추가하세요.")


def run(args):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args])
    if r.returncode:
        sys.exit("ffmpeg 오류 — 위 메시지를 확인하세요")


def video(path: Path, sec: int, bg: str, big: str, small: str, f: str, countdown=False, silent=False):
    text_color = "0x0B1120" if bg.startswith("0xA6") or bg.startswith("0x00E5") or bg.startswith("0xFF2B") else "white"
    big_text = "%{eif\\:" + str(sec) + "-t\\:d}" if countdown else big
    vf = (f"drawtext=fontfile='{f}':text='{big_text}':fontsize=150:fontcolor={text_color}:x=(w-tw)/2:y=(h-th)/2-60,"
          f"drawtext=fontfile='{f}':text='{small}':fontsize=48:fontcolor={text_color}:x=(w-tw)/2:y=h/2+90,"
          f"drawtext=fontfile='{f}':text='테스트 영상 · %{{eif\\:t\\:d}}s / {sec}s':fontsize=32:fontcolor={text_color}@0.7:x=40:y=h-70")
    args = ["-f", "lavfi", "-i", f"color=c={bg}:s=1280x720:r=30:d={sec}"]
    if not silent:
        args += ["-f", "lavfi", "-i", f"sine=frequency=440:beep_factor=2:duration={sec}", "-af", "volume=0.15"]
    args += ["-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p"]
    args += ["-an"] if silent else ["-c:a", "aac", "-shortest"]
    run(args + [str(path)])


def main():
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg이 없습니다. Windows: winget install Gyan.FFmpeg (설치 후 터미널을 새로 여세요)")
    OUT.mkdir(parents=True, exist_ok=True)
    f = font()
    made = []
    for name, sec, bg, big, small in ITEMS:
        p = OUT / name
        if p.exists() and not FORCE:
            continue
        video(p, 10 if SHORT else sec, bg, big, small, f, countdown=(name == "countdown.mp4"))
        made.append(name)
    loop = OUT / "anchor_loop.mp4"
    if FORCE or not loop.exists():
        video(loop, 10, "0x1A2440", "AI 앵커", "앵커 자리 반복 영상", f, silent=True)
        made.append(loop.name)
    bgm = OUT / "bgm.mp3"
    if FORCE or not bgm.exists():
        run(["-f", "lavfi", "-i", "sine=frequency=220:duration=60", "-f", "lavfi", "-i", "sine=frequency=330:duration=60",
             "-filter_complex", "[0][1]amix=inputs=2,volume=0.2,afade=t=in:d=2", "-c:a", "libmp3lame", str(bgm)])
        made.append(bgm.name)
    print(f"만든 파일 {len(made)}개 → {OUT}")
    for m in made:
        print("  ", m)
    print("큐시트 화면(/onair/control)의 '영상 파일' 칸이 모두 '준비됨'이 되면 끝입니다.")


if __name__ == "__main__":
    main()
