"""FastAPI 前端：上传文案 -> 后台生成 -> 进度轮询 -> 下载视频。

启动：
    uvicorn app:app --reload --port 8000
然后浏览器打开 http://localhost:8000
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse

from src import pipeline
from src.config import settings, MINIMAX_VOICES, MINIMAX_VOICE_IDS, THEMES

app = FastAPI(title="AI 课程视频生成系统")

RUNS = Path("runs")
RUNS.mkdir(exist_ok=True)

# job_id -> {progress, message, status, result/error}
JOBS: dict[str, dict] = {}


def _worker(job_id: str, text: str, subtitle: bool, theme: str, voice: str):
    job = JOBS[job_id]
    run_dir = RUNS / job_id

    def cb(p: float, m: str):
        job["progress"] = round(p, 3)
        job["message"] = m

    try:
        job["status"] = "running"
        result = pipeline.run(text, run_dir, progress_cb=cb, subtitle=subtitle, theme=theme, voice=voice)
        job["status"] = "done"
        job["result"] = result
        job["progress"] = 1.0
        job["message"] = "完成"
    except Exception as e:  # noqa: BLE001
        job["status"] = "error"
        job["error"] = str(e)
        job["message"] = f"出错: {e}"


@app.post("/api/generate")
async def generate(
    file: UploadFile | None = File(default=None),
    text: str = Form(default=""),
    subtitle: bool = Form(default=True),
    theme: str = Form(default="apple"),
    voice: str = Form(default=""),
):
    content = text.strip()
    if file is not None:
        content = (await file.read()).decode("utf-8", errors="ignore").strip()
    if not content:
        raise HTTPException(400, "请上传文案文件或粘贴文案内容")

    theme = theme if theme in THEMES else "apple"
    voice = voice if voice in MINIMAX_VOICE_IDS else settings.minimax_voice
    job_id = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]
    JOBS[job_id] = {"progress": 0.0, "message": "排队中…", "status": "queued"}
    threading.Thread(target=_worker, args=(job_id, content, subtitle, theme, voice), daemon=True).start()
    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
async def status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    return JSONResponse(job)


@app.get("/api/video/{job_id}")
async def video(job_id: str):
    job = JOBS.get(job_id)
    if not job or job.get("status") != "done":
        raise HTTPException(404, "视频尚未就绪")
    path = Path(job["result"]["video"])
    if not path.exists():
        raise HTTPException(404, "视频文件丢失")
    return FileResponse(path, media_type="video/mp4", filename=f"{job_id}.mp4")


@app.get("/api/pptx/{job_id}")
async def pptx(job_id: str):
    job = JOBS.get(job_id)
    if not job or job.get("status") != "done":
        raise HTTPException(404, "PPT 尚未就绪")
    p = job["result"].get("pptx")
    if not p or not Path(p).exists():
        raise HTTPException(404, "PPT 文件不存在")
    return FileResponse(
        p,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=f"{job_id}.pptx",
    )


@app.get("/", response_class=HTMLResponse)
async def index():
    llm_label = f"OpenAI · {settings.openai_model}" if settings.llm_available() else "规则兜底（未配置 Key）"
    opts = []
    for vid, name, desc in MINIMAX_VOICES:
        sel = " selected" if vid == settings.minimax_voice else ""
        opts.append(f'<option value="{vid}"{sel}>{name} · {desc}</option>')

    chips = []
    for key, th in THEMES.items():
        active = " active" if key == settings.theme_name else ""
        text_col = "#fff" if max(th.bg_top) < 128 else "#1d1d1f"
        chips.append(
            f'<button type="button" data-theme="{key}" class="chip{active}">'
            f'<span class="dot" style="background:{th.swatch}"></span>{th.label}</button>'
        )
    return (
        HTML.replace("{{LLM}}", llm_label)
        .replace("{{TTS}}", settings.tts_provider)
        .replace("{{VOICES}}", "".join(opts))
        .replace("{{THEMES}}", "".join(chips))
    )


HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>AI 课程视频生成</title>
<style>
  :root{
    --bg:#fbfbfd; --surface:#ffffff; --line:#d2d2d7;
    --ink:#1d1d1f; --muted:#6e6e73; --blue:#0071e3; --blue-d:#0077ed;
  }
  *{box-sizing:border-box;}
  html,body{margin:0;}
  body{
    font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI","Microsoft YaHei",sans-serif;
    background:var(--bg); color:var(--ink); min-height:100vh;
    -webkit-font-smoothing:antialiased;
  }
  .wrap{max-width:820px;margin:0 auto;padding:72px 24px 96px;}
  .hero{text-align:center;margin-bottom:44px;}
  h1{font-size:48px;line-height:1.07;letter-spacing:-.02em;font-weight:600;margin:0 0 14px;}
  .hero p{font-size:20px;color:var(--muted);margin:0;font-weight:400;}
  .badges{display:flex;gap:8px;justify-content:center;margin-top:20px;flex-wrap:wrap;}
  .badge{font-size:12.5px;color:var(--muted);background:#f5f5f7;border-radius:980px;padding:6px 14px;}
  .card{background:var(--surface);border:1px solid var(--line);border-radius:20px;padding:28px;margin-bottom:22px;box-shadow:0 1px 3px rgba(0,0,0,.04);}
  .label{font-size:13px;font-weight:600;color:var(--muted);margin:0 0 10px;letter-spacing:.01em;}
  textarea{width:100%;min-height:190px;background:#fff;border:1px solid var(--line);border-radius:14px;color:var(--ink);padding:16px;font-size:15px;line-height:1.7;resize:vertical;font-family:inherit;}
  textarea:focus{outline:none;border-color:var(--blue);box-shadow:0 0 0 4px rgba(0,113,227,.12);}
  .field{margin-top:22px;}
  .file-row{display:flex;align-items:center;gap:12px;}
  .file-btn{font-size:14px;color:var(--blue);cursor:pointer;font-weight:500;}
  input[type=file]{display:none;}
  .fname{font-size:13px;color:var(--muted);}
  /* 主题选择：可换行的色卡 chips */
  .chips{display:flex;flex-wrap:wrap;gap:10px;}
  .chip{display:inline-flex;align-items:center;border:1px solid var(--line);background:#fff;color:var(--ink);font-size:14px;font-weight:500;padding:9px 16px;border-radius:980px;cursor:pointer;transition:.15s;font-family:inherit;}
  .chip:hover{border-color:#b9b9c0;}
  .chip.active{border-color:var(--blue);box-shadow:0 0 0 3px rgba(0,113,227,.14);}
  .chip .dot{display:inline-block;width:14px;height:14px;border-radius:50%;margin-right:8px;border:1px solid rgba(0,0,0,.12);}
  /* 下拉选择 */
  .select-wrap{position:relative;display:block;}
  select{appearance:none;-webkit-appearance:none;width:100%;background:#fff;border:1px solid var(--line);border-radius:12px;padding:13px 40px 13px 16px;font-size:15px;color:var(--ink);font-family:inherit;cursor:pointer;}
  select:focus{outline:none;border-color:var(--blue);box-shadow:0 0 0 4px rgba(0,113,227,.12);}
  .select-wrap:after{content:"⌄";position:absolute;right:16px;top:46%;transform:translateY(-50%);color:var(--muted);pointer-events:none;font-size:18px;}
  /* 开关 */
  .switch{position:relative;display:inline-block;width:46px;height:28px;}
  .switch input{opacity:0;width:0;height:0;}
  .slider{position:absolute;inset:0;background:#e3e3e8;border-radius:980px;transition:.2s;cursor:pointer;}
  .slider:before{content:"";position:absolute;height:24px;width:24px;left:2px;top:2px;background:#fff;border-radius:50%;transition:.2s;box-shadow:0 1px 3px rgba(0,0,0,.2);}
  .switch input:checked + .slider{background:#34c759;}
  .switch input:checked + .slider:before{transform:translateX(18px);}
  .toggle-row{display:flex;align-items:center;justify-content:space-between;}
  .toggle-row .t{font-size:15px;}
  .actions{text-align:center;margin-top:8px;}
  .btn{background:var(--blue);color:#fff;border:0;border-radius:980px;padding:14px 40px;font-size:17px;font-weight:500;cursor:pointer;transition:.15s;font-family:inherit;}
  .btn:hover{background:var(--blue-d);}
  .btn:disabled{opacity:.4;cursor:not-allowed;}
  .progress{height:6px;background:#e9e9ec;border-radius:980px;overflow:hidden;}
  .bar{height:100%;width:0;background:var(--blue);border-radius:980px;transition:width .3s;}
  .pmsg{color:var(--muted);font-size:14px;margin-top:14px;text-align:center;}
  video{width:100%;border-radius:16px;margin-top:4px;background:#000;display:block;}
  .stats{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:20px;}
  .stat{text-align:center;}
  .stat b{display:block;font-size:28px;font-weight:600;letter-spacing:-.02em;}
  .stat span{font-size:13px;color:var(--muted);}
  .dl{display:block;text-align:center;margin-top:22px;}
  .dl a{color:var(--blue);text-decoration:none;font-size:16px;font-weight:500;}
  .warn{background:#fff4e5;border:1px solid #ffd08a;color:#8a5a00;border-radius:12px;padding:12px 16px;font-size:14px;margin-bottom:16px;line-height:1.6;}
  .hidden{display:none;}
</style>
</head>
<body>
<div class="wrap">
  <div class="hero">
    <h1>课程视频，自动生成。</h1>
    <p>输入一篇上课文案，自动产出带配音、重点高亮与字幕的讲解视频。</p>
    <div class="badges">
      <span class="badge">LLM · {{LLM}}</span>
      <span class="badge">TTS · {{TTS}}</span>
    </div>
  </div>

  <div class="card">
    <div class="label">上课文案</div>
    <textarea id="text" placeholder="在此粘贴上课文案，或选择 .txt 文件…"></textarea>

    <div class="field">
      <div class="file-row">
        <label class="file-btn" for="file">＋ 选择文件</label>
        <input type="file" id="file" accept=".txt"/>
        <span class="fname" id="fname">未选择文件</span>
      </div>
    </div>

    <div class="field">
      <div class="label">PPT 风格</div>
      <div class="chips" id="seg">{{THEMES}}</div>
    </div>

    <div class="field">
      <div class="label">配音音色（MiniMax）</div>
      <div class="select-wrap">
        <select id="voice">{{VOICES}}</select>
      </div>
    </div>

    <div class="field toggle-row">
      <span class="t">叠加字幕</span>
      <label class="switch"><input type="checkbox" id="subtitle" checked/><span class="slider"></span></label>
    </div>
  </div>

  <div class="actions">
    <button class="btn" id="go">开始生成</button>
  </div>

  <div class="card hidden" id="prog-card" style="margin-top:22px;">
    <div class="progress"><div class="bar" id="bar"></div></div>
    <div class="pmsg" id="pmsg">准备中…</div>
  </div>

  <div class="card hidden" id="result-card">
    <div id="warn" class="warn hidden"></div>
    <video id="video" controls></video>
    <div class="stats" id="stats"></div>
    <div class="dl">
      <a id="dl" href="#" download>下载 MP4 ↓</a>
      <a id="dlppt" href="#" download style="margin-left:24px;">下载 PPT ↓</a>
    </div>
  </div>
</div>

<script>
const $ = id => document.getElementById(id);
let timer = null;
const activeChip = document.querySelector("#seg .chip.active") || document.querySelector("#seg .chip");
let theme = activeChip ? activeChip.dataset.theme : "apple";

document.querySelectorAll("#seg .chip").forEach(b => {
  b.onclick = () => {
    document.querySelectorAll("#seg .chip").forEach(x => x.classList.remove("active"));
    b.classList.add("active");
    theme = b.dataset.theme;
  };
});

$("file").onchange = () => {
  $("fname").textContent = $("file").files[0] ? $("file").files[0].name : "未选择文件";
};

$("go").onclick = async () => {
  const text = $("text").value.trim();
  const file = $("file").files[0];
  if(!text && !file){ alert("请粘贴文案或选择文件"); return; }
  const fd = new FormData();
  if(file) fd.append("file", file);
  fd.append("text", text);
  fd.append("subtitle", $("subtitle").checked);
  fd.append("theme", theme);
  fd.append("voice", $("voice").value);

  $("go").disabled = true;
  $("prog-card").classList.remove("hidden");
  $("result-card").classList.add("hidden");
  setBar(0.02, "提交任务…");

  const r = await fetch("/api/generate", {method:"POST", body:fd});
  if(!r.ok){ const e = await r.json(); alert(e.detail||"提交失败"); $("go").disabled=false; return; }
  const {job_id} = await r.json();
  poll(job_id);
};

function setBar(p, msg){
  $("bar").style.width = (p*100).toFixed(1)+"%";
  $("pmsg").textContent = msg + "  ·  " + (p*100).toFixed(0) + "%";
}

function poll(job_id){
  timer = setInterval(async () => {
    const r = await fetch("/api/status/"+job_id);
    const j = await r.json();
    setBar(j.progress||0, j.message||"");
    if(j.status === "done"){
      clearInterval(timer);
      showResult(job_id, j.result);
      $("go").disabled = false;
    } else if(j.status === "error"){
      clearInterval(timer);
      $("pmsg").textContent = "生成失败：" + (j.error||"");
      $("go").disabled = false;
    }
  }, 1200);
}

function showResult(job_id, res){
  $("result-card").classList.remove("hidden");
  const url = "/api/video/"+job_id;
  $("video").src = url;
  $("dl").href = url;
  $("dlppt").href = "/api/pptx/"+job_id;
  $("dlppt").style.display = res.pptx ? "inline" : "none";
  if(res.warning){
    $("warn").textContent = "⚠ " + res.warning + "（PPT/讲解质量会下降，请检查 API Key 后重试）";
    $("warn").classList.remove("hidden");
  } else {
    $("warn").classList.add("hidden");
  }
  $("stats").innerHTML = `
    <div class="stat"><b>${res.slides}</b><span>页 PPT</span></div>
    <div class="stat"><b>${res.video_seconds}s</b><span>视频时长</span></div>
    <div class="stat"><b>${res.elapsed_seconds}s</b><span>生成耗时</span></div>`;
}
</script>
</body>
</html>"""
