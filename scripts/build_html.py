#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将标准题库 bank.json 内联进 index.html，并生成 PWA 所需的 manifest.json、sw.js。

设计：
- 题库数据以 JS 变量形式内联（window.__BANK__），避免 file:// 协议下 fetch 被 CORS 拦截
- 网页逻辑、样式全部内联进 index.html，单文件零依赖
- 图片走外部 CDN 绝对URL，由 Service Worker 懒缓存
- 额外输出 manifest.json / sw.js 以支持 PWA（离线、可安装）

运行: python3 scripts/build_html.py
产出: index.html, manifest.json, sw.js, icon-192.png, icon-512.png, favicon.png
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK = os.path.join(ROOT, "data", "bank.json")
OUT_HTML = os.path.join(ROOT, "index.html")
OUT_MANIFEST = os.path.join(ROOT, "manifest.json")
OUT_SW = os.path.join(ROOT, "sw.js")
OUT_ICON_192 = os.path.join(ROOT, "icon-192.png")
OUT_ICON_512 = os.path.join(ROOT, "icon-512.png")
OUT_FAVICON = os.path.join(ROOT, "favicon.png")

# 构建版本号（用于 Service Worker 缓存失效）
import time
BUILD_VER = time.strftime("%Y%m%d%H%M%S")

# index.html 模板（占位符 __BANK_JSON__ 会被替换为题库数据）
TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<meta name="theme-color" content="#1e80ff">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="科目一">
<link rel="manifest" href="manifest.json">
<link rel="apple-touch-icon" href="icon-192.png">
<link rel="icon" type="image/png" sizes="192x192" href="icon-192.png">
<link rel="icon" type="image/png" sizes="512x512" href="icon-512.png">
<title>C1 驾照 · 科目一模拟考试</title>
<style>
:root{
  --blue:#1e80ff; --blue-dark:#1660d8; --blue-light:#e8f2ff;
  --green:#07c160; --red:#fa5151; --orange:#ff976a; --purple:#7a4dd0;
  --gray-1:#f7f8fa; --gray-2:#f0f1f5; --gray-3:#dcdee0;
  --gray-5:#969799; --gray-6:#646566; --gray-7:#323233; --gray-8:#1a1a1a;
  --radius:10px; --shadow:0 2px 12px rgba(0,0,0,.06);
  --safe-top:env(safe-area-inset-top,0px);
  --safe-bottom:env(safe-area-inset-bottom,0px);
}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html,body{height:100%}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;background:var(--gray-1);color:var(--gray-8);line-height:1.6;font-size:15px;padding-top:var(--safe-top);padding-bottom:var(--safe-bottom)}
.hidden{display:none!important}
button{font-family:inherit;cursor:pointer;border:none;background:none}
.wrap{max-width:880px;margin:0 auto;padding:0 14px}

/* ===== 封面页 ===== */
.cover{padding:32px 16px 48px;text-align:center}
.cover .logo{width:84px;height:84px;border-radius:20px;background:linear-gradient(135deg,var(--blue),var(--blue-dark));margin:0 auto 16px;display:flex;align-items:center;justify-content:center;font-size:42px;color:#fff;box-shadow:var(--shadow)}
.cover h1{font-size:24px;margin-bottom:6px;letter-spacing:.5px}
.cover .sub{color:var(--gray-6);margin-bottom:22px;font-size:14px}
.mode-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;max-width:480px;margin:0 auto 14px}
.mode-card{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;background:#fff;border-radius:14px;padding:22px 12px;box-shadow:var(--shadow);transition:transform .12s;min-height:118px}
.mode-card:active{transform:scale(.97)}
.mode-card .ic{font-size:34px;line-height:1}
.mode-card .t{font-size:16px;font-weight:600;color:var(--gray-8)}
.mode-card .d{font-size:12px;color:var(--gray-5)}
.mode-card.practice .ic{color:var(--blue)}
.mode-card.exam .ic{color:var(--orange)}
.mode-card.wrong{grid-column:1/3;flex-direction:row;justify-content:space-between;padding:16px 20px;min-height:auto;background:linear-gradient(135deg,#fff5f0,#fff);border:1px solid #ffd9c2}
.mode-card.wrong .info{text-align:left;display:flex;flex-direction:column;gap:2px}
.mode-card.wrong .badge{background:var(--red);color:#fff;border-radius:20px;padding:4px 14px;font-size:13px;font-weight:600;min-width:36px;text-align:center}
.mode-card.wrong.disabled{opacity:.5;filter:grayscale(.6)}
.mode-card.wrong.disabled:active{transform:none}
.stats-row{display:flex;justify-content:center;gap:0;flex-wrap:wrap;margin:22px auto 18px;max-width:560px;background:#fff;border-radius:var(--radius);box-shadow:var(--shadow);overflow:hidden}
.stats-row .stat{flex:1;min-width:80px;padding:14px 8px;text-align:center;border-right:1px solid var(--gray-2)}
.stats-row .stat:last-child{border-right:none}
.stats-row .stat .n{font-size:19px;font-weight:600;color:var(--blue);display:block}
.stats-row .stat .n.green{color:var(--green)}
.stats-row .stat .l{font-size:11px;color:var(--gray-6);margin-top:2px}
.btn{display:inline-block;background:var(--blue);color:#fff;padding:13px 38px;border-radius:24px;font-size:16px;font-weight:500;transition:all .15s;box-shadow:0 4px 12px rgba(30,128,255,.3)}
.btn:active{transform:translateY(1px)}
.btn.ghost{background:#fff;color:var(--blue);box-shadow:0 0 0 1px var(--blue) inset}
.btn.gray{background:var(--gray-2);color:var(--gray-7);box-shadow:none}
.btn.danger{background:#fff;color:var(--red);box-shadow:0 0 0 1px var(--red) inset}
.btn:disabled{opacity:.5;cursor:not-allowed}
.btn.small{padding:8px 18px;font-size:13px;border-radius:18px}
.btn.full{display:block;width:100%}
.link-btn{color:var(--blue);font-size:13px;padding:6px 10px;display:inline-block}
.info-box{background:#fffbe8;border:1px solid #ffe58f;border-radius:var(--radius);padding:12px 14px;font-size:13px;color:#8a6d3b;text-align:left;margin:14px auto;max-width:560px;line-height:1.7}
.info-box b{color:#a87830}
.rule-box{background:#fff;border-radius:var(--radius);padding:16px 18px;text-align:left;margin:14px auto;max-width:560px;box-shadow:var(--shadow);font-size:13px;color:var(--gray-7)}
.rule-box h3{font-size:14px;margin-bottom:8px;color:var(--gray-8)}
.rule-box ul{padding-left:18px}
.rule-box li{margin:3px 0}
.rule-box details{margin-top:10px;border-top:1px dashed var(--gray-3);padding-top:10px}
.rule-box summary{cursor:pointer;color:var(--blue);font-size:13px}

/* 进度条（首页学习进度可视化） */
.progress-bar{max-width:560px;margin:14px auto 0;background:#fff;border-radius:var(--radius);box-shadow:var(--shadow);padding:14px 16px}
.progress-bar .top{display:flex;justify-content:space-between;font-size:12px;color:var(--gray-6);margin-bottom:6px}
.progress-bar .track{height:8px;background:var(--gray-2);border-radius:4px;overflow:hidden}
.progress-bar .fill{height:100%;background:linear-gradient(90deg,var(--blue),var(--green));width:0;transition:width .4s;border-radius:4px}
.progress-bar .meta{font-size:11px;color:var(--gray-5);margin-top:6px}

/* ===== 答题页 ===== */
.exam-header{position:sticky;top:0;background:#fff;border-bottom:1px solid var(--gray-2);padding:10px 0;z-index:20;margin-top:var(--safe-top)}
.exam-header .row{display:flex;align-items:center;justify-content:space-between;gap:10px}
.exam-header .progress{flex:1;height:6px;background:var(--gray-2);border-radius:3px;overflow:hidden}
.exam-header .progress > i{display:block;height:100%;background:var(--blue);width:0;transition:width .2s}
.exam-header .timer{font-variant-numeric:tabular-nums;font-weight:600;color:var(--gray-7);font-size:14px;white-space:nowrap}
.exam-header .timer.warn{color:var(--red)}
.exam-header .meta{font-size:13px;color:var(--gray-6);margin-top:4px;display:flex;align-items:center;gap:4px;flex-wrap:wrap}
.exam-header .meta b{color:var(--blue)}
.mode-badge{display:inline-block;font-size:11px;padding:2px 8px;border-radius:4px;font-weight:600}
.mode-badge.practice{color:var(--blue);background:var(--blue-light)}
.mode-badge.exam{color:var(--orange);background:#fff5f0}
.mode-badge.wrong{color:var(--red);background:#fdeaea}

.q-wrap{padding:18px 0 30px}
.q-tag{display:inline-block;font-size:11px;color:var(--blue);background:var(--blue-light);padding:2px 8px;border-radius:4px;margin-bottom:10px}
.q-tag.judge{color:#7a4dd0;background:#f1e9ff}
.q-no{color:var(--gray-5);font-size:13px;margin-bottom:6px}
.q-no b{color:var(--gray-8);font-size:15px}
.q-text{font-size:17px;line-height:1.7;color:var(--gray-8);margin-bottom:16px;word-break:break-word}
.q-image{max-width:100%;max-height:280px;border-radius:8px;margin-bottom:16px;display:block;background:var(--gray-2);box-shadow:var(--shadow)}
.q-image.loading{min-height:120px}
.opts{display:flex;flex-direction:column;gap:10px;margin-bottom:16px}
.opt{display:flex;align-items:center;gap:10px;padding:13px 14px;background:#fff;border:1.5px solid var(--gray-3);border-radius:var(--radius);transition:all .12s;text-align:left;width:100%;font-size:15px;color:var(--gray-8);min-height:48px}
.opt:active{transform:scale(.99)}
.opt .k{flex-shrink:0;width:26px;height:26px;border-radius:50%;border:1.5px solid var(--gray-3);display:flex;align-items:center;justify-content:center;font-size:13px;color:var(--gray-6);font-weight:600}
.opt.selected{border-color:var(--blue);background:var(--blue-light)}
.opt.selected .k{border-color:var(--blue);background:var(--blue);color:#fff}
.opt.correct{border-color:var(--green);background:#e9f9f0}
.opt.correct .k{border-color:var(--green);background:var(--green);color:#fff}
.opt.wrong{border-color:var(--red);background:#fdeaea}
.opt.wrong .k{border-color:var(--red);background:var(--red);color:#fff}
.opt.disabled{cursor:default}

/* 刷题模式即时反馈卡片 */
.feedback{border-radius:var(--radius);padding:14px;margin-top:6px;animation:fadeIn .2s}
.feedback.right{background:#e9f9f0;border:1px solid #b7ebd2}
.feedback.wrong{background:#fdeaea;border:1px solid #ffccc7}
.feedback .fb-title{font-size:14px;font-weight:600;margin-bottom:8px;display:flex;align-items:center;gap:6px}
.feedback.right .fb-title{color:var(--green)}
.feedback.wrong .fb-title{color:var(--red)}
.feedback .ans-line{font-size:13px;margin-bottom:4px}
.feedback .ans-line .your.wrong{color:var(--red);font-weight:600}
.feedback .ans-line .correct{color:var(--green);font-weight:600}
.feedback .exp{background:#fff;border-radius:6px;padding:9px 11px;font-size:12.5px;color:var(--gray-7);line-height:1.7;margin-top:8px}
.feedback .exp b{color:var(--gray-8)}
.feedback .law{margin-top:6px;border-left:3px solid var(--blue);padding-left:8px}
.feedback .updated{display:inline-block;font-size:11px;color:#a87830;background:#fffbe8;border:1px solid #ffe58f;padding:1px 6px;border-radius:3px;margin-left:6px}
@keyframes fadeIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}

.exam-nav{display:flex;gap:10px;align-items:center;justify-content:space-between;padding:14px 0 6px;border-top:1px solid var(--gray-2);position:sticky;bottom:0;background:var(--gray-1)}
.exam-nav .grow{flex:1}
.mark-btn{color:var(--orange);font-size:13px;padding:8px 4px}
.mark-btn.active{font-weight:600}
.sheet-toggle{color:var(--blue);font-size:13px;padding:8px 4px}

/* ===== 答题卡浮层 ===== */
.sheet-mask{position:fixed;inset:0;background:rgba(0,0,0,.4);z-index:30;display:none}
.sheet-mask.show{display:block}
.sheet{position:fixed;left:0;right:0;bottom:0;background:#fff;border-radius:16px 16px 0 0;padding:16px 16px calc(24px + var(--safe-bottom));z-index:31;transform:translateY(100%);transition:transform .25s;max-height:75vh;overflow:auto}
.sheet.show{transform:translateY(0)}
.sheet h4{font-size:14px;margin-bottom:12px;color:var(--gray-7);display:flex;justify-content:space-between;align-items:center}
.sheet h4 .close{font-size:13px;color:var(--gray-5)}
.sheet-legend{display:flex;gap:12px;font-size:11px;color:var(--gray-6);margin-bottom:12px;flex-wrap:wrap}
.sheet-legend span{display:flex;align-items:center;gap:4px}
.sheet-legend i{width:14px;height:14px;border-radius:3px;display:inline-block;border:1px solid var(--gray-3)}
.sheet-grid{display:grid;grid-template-columns:repeat(10,1fr);gap:6px}
.sheet-grid button{aspect-ratio:1;border:1px solid var(--gray-3);border-radius:5px;font-size:13px;color:var(--gray-7);background:#fff}
.sheet-grid button.answered{background:var(--blue);color:#fff;border-color:var(--blue)}
.sheet-grid button.right{background:var(--green);color:#fff;border-color:var(--green)}
.sheet-grid button.wrong{background:var(--red);color:#fff;border-color:var(--red)}
.sheet-grid button.marked{border-color:var(--orange);color:var(--orange)}
.sheet-grid button.marked.answered{background:var(--orange);color:#fff}
.sheet-grid button.current{outline:2px solid var(--blue);outline-offset:1px}

/* ===== 结果页 ===== */
.result{padding:30px 16px 48px;text-align:center}
.result .score-ring{width:160px;height:160px;margin:0 auto 18px;position:relative}
.result .score-ring svg{transform:rotate(-90deg)}
.result .score-ring .num{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center}
.result .score-ring .num b{font-size:44px;line-height:1;color:var(--gray-8)}
.result .score-ring .num span{font-size:12px;color:var(--gray-6);margin-top:2px}
.result .verdict{font-size:20px;font-weight:600;margin-bottom:8px}
.result .verdict.pass{color:var(--green)}
.result .verdict.fail{color:var(--red)}
.result .verdict-sub{color:var(--gray-6);font-size:14px;margin-bottom:20px}
.result .summary{display:flex;justify-content:center;gap:12px;flex-wrap:wrap;margin-bottom:24px}
.result .summary .item{background:#fff;border-radius:var(--radius);padding:10px 16px;box-shadow:var(--shadow);min-width:78px}
.result .summary .item .n{font-size:20px;font-weight:600;display:block}
.result .summary .item .l{font-size:12px;color:var(--gray-6)}
.result .summary .item .n.right{color:var(--green)}
.result .summary .item .n.wrong{color:var(--red)}

.review{margin-top:8px;text-align:left}
.review h3{font-size:15px;color:var(--gray-7);margin:16px 0 10px;text-align:center}
.review-filter{text-align:center;margin-bottom:12px}
.review-filter button{font-size:12px;padding:5px 12px;border-radius:14px;margin:0 3px;border:1px solid var(--gray-3);background:#fff;color:var(--gray-6)}
.review-filter button.active{background:var(--blue);color:#fff;border-color:var(--blue)}
.rv-item{background:#fff;border-radius:var(--radius);padding:14px;margin-bottom:10px;box-shadow:var(--shadow);border-left:3px solid var(--gray-3)}
.rv-item.wrong{border-left-color:var(--red)}
.rv-item.right{border-left-color:var(--green)}
.rv-head{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin-bottom:8px}
.rv-head .t{font-size:11px;color:var(--gray-5);flex-shrink:0}
.rv-head .t.wrong{color:var(--red)}
.rv-head .t.right{color:var(--green)}
.rv-q{font-size:14px;color:var(--gray-8);line-height:1.6;margin-bottom:8px}
.rv-q img{max-width:100%;max-height:200px;border-radius:6px;margin-top:6px}
.rv-ans{font-size:13px;margin-bottom:6px}
.rv-ans .your.wrong{color:var(--red)}
.rv-ans .your.right{color:var(--green)}
.rv-ans .correct{color:var(--green)}
.rv-exp{background:var(--gray-1);border-radius:6px;padding:8px 10px;font-size:12.5px;color:var(--gray-7);line-height:1.6;margin-top:6px}
.rv-exp b{color:var(--gray-8)}
.rv-updated{display:inline-block;font-size:11px;color:#a87830;background:#fffbe8;border:1px solid #ffe58f;padding:1px 6px;border-radius:3px;margin-left:6px}

/* 预下载图片浮层 */
.dl-mask{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:40;display:none;align-items:center;justify-content:center}
.dl-mask.show{display:flex}
.dl-box{background:#fff;border-radius:14px;padding:22px 20px;width:84%;max-width:340px;text-align:center}
.dl-box h4{font-size:16px;margin-bottom:8px}
.dl-box .dl-sub{font-size:12.5px;color:var(--gray-6);margin-bottom:16px;line-height:1.6}
.dl-box .dl-track{height:8px;background:var(--gray-2);border-radius:4px;overflow:hidden;margin-bottom:8px}
.dl-box .dl-fill{height:100%;background:var(--blue);width:0;transition:width .15s;border-radius:4px}
.dl-box .dl-num{font-size:13px;color:var(--gray-7);margin-bottom:14px;font-variant-numeric:tabular-nums}

.foot{text-align:center;padding:18px 16px 30px;color:var(--gray-5);font-size:11px;line-height:1.8}
.foot a{color:var(--blue)}

@media(max-width:520px){
  .cover h1{font-size:21px}
  .q-text{font-size:15px}
  .sheet-grid{grid-template-columns:repeat(8,1fr)}
  .result .score-ring{width:140px;height:140px}
  .mode-card{min-height:104px;padding:18px 10px}
  .mode-card .ic{font-size:30px}
}
</style>
</head>
<body>

<!-- ============ 封面页 ============ -->
<section id="page-cover" class="wrap cover">
  <div class="logo">🚗</div>
  <h1>C1 驾照 · 科目一</h1>
  <p class="sub">智能刷题 + 模拟考试 · 离线可用</p>

  <div class="mode-grid">
    <button class="mode-card practice" id="btn-practice">
      <span class="ic">📚</span>
      <span class="t">刷题练习</span>
      <span class="d">智能精选 即时解析</span>
    </button>
    <button class="mode-card exam" id="btn-exam">
      <span class="ic">📝</span>
      <span class="t">模拟考试</span>
      <span class="d">限时45分钟</span>
    </button>
    <button class="mode-card wrong disabled" id="btn-wrong">
      <div class="info">
        <span class="ic" style="font-size:24px">❌</span>
        <span class="t" style="font-size:15px">错题重练</span>
        <span class="d" id="wrong-desc">暂无待复习题</span>
      </div>
      <span class="badge" id="wrong-badge">0</span>
    </button>
  </div>

  <div class="progress-bar">
    <div class="top"><span>学习进度</span><span id="cv-progress-pct">0%</span></div>
    <div class="track"><i class="fill" id="cv-progress-fill"></i></div>
    <div class="meta" id="cv-progress-meta">已学 0 / — 题</div>
  </div>

  <div class="stats-row">
    <div class="stat"><span class="n" id="cv-bank">—</span><span class="l">题库总量</span></div>
    <div class="stat"><span class="n green" id="cv-mastered">0</span><span class="l">已掌握</span></div>
    <div class="stat"><span class="n" id="cv-accuracy">—</span><span class="l">正确率</span></div>
    <div class="stat"><span class="n" id="cv-streak">0天</span><span class="l">连续学习</span></div>
  </div>

  <div style="margin-top:14px">
    <button class="btn ghost small" id="btn-predl">📥 预下载图片库</button>
    <button class="btn ghost small" id="btn-reset" style="margin-left:6px">↺ 重置进度</button>
  </div>

  <div class="rule-box">
    <h3>📌 三种模式说明</h3>
    <ul>
      <li><b>刷题练习</b>：基于 SM-2 间隔重复算法智能抽题，优先复习今日到期题目 + 引入新题，答题即时判定并展示解析，专注薄弱点</li>
      <li><b>模拟考试</b>：判断40+单选60共100题，限时45分钟，对标真实上机考试，交卷后统一评定</li>
      <li><b>错题重练</b>：复习 SM-2 算法判定今日到期的题目，答对推进间隔，答错重置</li>
    </ul>
    <details>
      <summary>SM-2 间隔重复算法原理</summary>
      <p style="margin-top:8px;font-size:12.5px;color:var(--gray-6);line-height:1.7">
      每题记录难度系数(ease)与复习间隔。答对一题，下次复习间隔会变长（1天→3天→7天→16天→35天…），避免重复刷已掌握的题；答错则重置间隔、降低难度系数，确保薄弱题频繁出现。科学依据艾宾浩斯遗忘曲线，用最少时间巩固最多知识点。
      </p>
    </details>
  </div>

  <div class="info-box">
    <b>⚠️ 时效性说明</b><br>
    本题库对应公安部 2022年7月题库（GA/T 1575），已按 <b>2025年1月第172号令</b> 修订年龄相关题目。<b>新能源汽车等2025新增考点未收录</b>，建议考前用驾考App补充。图片题自动缓存可离线查看。
  </div>
</section>

<!-- ============ 答题页 ============ -->
<section id="page-exam" class="hidden">
  <div class="exam-header">
    <div class="wrap">
      <div class="row">
        <div class="progress"><i id="pg-bar"></i></div>
        <div class="timer" id="timer">—</div>
      </div>
      <div class="meta">
        <span class="mode-badge practice hidden" id="mb-practice">刷题</span>
        <span class="mode-badge exam hidden" id="mb-exam">模考</span>
        <span class="mode-badge wrong hidden" id="mb-wrong">错题</span>
        第 <b id="cur-no">1</b> / <b id="cur-total">100</b> · 已答 <b id="cur-done">0</b> ·
        <button class="mark-btn" id="btn-mark">🚩 标记</button>
        <button class="sheet-toggle" id="btn-sheet">答题卡</button>
      </div>
    </div>
  </div>

  <div class="wrap q-wrap" id="q-area"></div>

  <div class="wrap exam-nav">
    <button class="btn gray grow" id="btn-prev">‹ 上一题</button>
    <button class="btn grow" id="btn-next">下一题 ›</button>
  </div>
</section>

<!-- 答题卡浮层 -->
<div class="sheet-mask" id="sheet-mask"></div>
<div class="sheet" id="sheet">
  <h4>答题卡 <button class="close" id="sheet-close">收起 ✕</button></h4>
  <div class="sheet-legend" id="sheet-legend">
    <span><i style="background:var(--blue);border-color:var(--blue)"></i>已答</span>
    <span><i></i>未答</span>
    <span><i style="border-color:var(--orange)"></i>标记</span>
  </div>
  <div class="sheet-grid" id="sheet-grid"></div>
  <div id="sheet-submit-wrap" style="margin-top:16px;text-align:center">
    <button class="btn" id="btn-submit">交卷</button>
  </div>
</div>

<!-- ============ 结果页 ============ -->
<section id="page-result" class="hidden">
  <div class="wrap result">
    <div class="score-ring">
      <svg width="160" height="160">
        <circle cx="80" cy="80" r="70" fill="none" stroke="#f0f1f5" stroke-width="12"/>
        <circle id="score-arc" cx="80" cy="80" r="70" fill="none" stroke="#07c160" stroke-width="12" stroke-linecap="round" stroke-dasharray="0 440"/>
      </svg>
      <div class="num"><b id="r-score">0</b><span>分</span></div>
    </div>
    <div class="verdict" id="r-verdict">—</div>
    <div class="verdict-sub" id="r-verdict-sub"></div>

    <div class="summary">
      <div class="item"><span class="n right" id="r-right">0</span><span class="l">答对</span></div>
      <div class="item"><span class="n wrong" id="r-wrong">0</span><span class="l">答错</span></div>
      <div class="item"><span class="n" id="r-time">0′</span><span class="l">用时</span></div>
    </div>

    <button class="btn" id="btn-again">再考一次</button>
    <button class="btn ghost" id="btn-result-home" style="margin-left:8px">返回首页</button>

    <div class="review-filter hidden" id="rv-filter">
      <button class="active" data-f="all">全部</button>
      <button data-f="wrong">仅错题</button>
    </div>
    <div class="review" id="review"></div>
  </div>
</section>

<!-- 预下载图片浮层 -->
<div class="dl-mask" id="dl-mask">
  <div class="dl-box">
    <h4 id="dl-title">📥 预下载图片库</h4>
    <div class="dl-sub" id="dl-sub">将下载全部题目图片至本地，支持离线查看刷题。预计约 50-100MB。</div>
    <div class="dl-track"><i class="dl-fill" id="dl-fill"></i></div>
    <div class="dl-num" id="dl-num">准备中…</div>
    <button class="btn gray small" id="dl-cancel">取消</button>
  </div>
</div>

<div class="foot">
  数据来源：开源项目 doupoa/DrivingTestSubjectOne（banban驾道，对应公安部 GA/T 1575）<br>
  仅供学习备考，请以最新交规与官方题库为准
</div>

<script>
window.__BANK__ = __BANK_JSON__;
window["__BUILD_VER__"] = "__BUILD_VER__";
</script>
<script>
(function(){
"use strict";

/* ============================================================
 * 基础工具
 * ============================================================ */
var BANK = window.__BANK__;
var BANK_BY_ID = {};
BANK.forEach(function(q){ BANK_BY_ID[q.id] = q; });
var CATS = ["law","signal","safety","operation","case"];
var DAY_MS = 86400000;

function $(id){return document.getElementById(id);}
function byTagFirst(id){return document.querySelector(id);}
function each(list, fn){ Array.prototype.forEach.call(list, fn); }
function shuffle(arr){
  var a = arr.slice();
  for(var i=a.length-1;i>0;i--){var j=Math.floor(Math.random()*(i+1));var t=a[i];a[i]=a[j];a[j]=t;}
  return a;
}
function escapeHtml(s){return (s==null?"":String(s)).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];});}
// 图片 URL：http 升级为 https，避免 HTTPS 页面下的 Mixed Content 警告
function imgUrl(u){ return u ? String(u).replace(/^http:\/\//i, "https://") : ""; }

function show(id){
  ["page-cover","page-exam","page-result"].forEach(function(p){
    $(p).classList.toggle("hidden", p!==id);
  });
  window.scrollTo(0,0);
}

/* ============================================================
 * 持久化层 (localStorage + Cache API)
 * ============================================================ */
var LS_SM2 = "kemuyi_sm2";
var LS_STATS = "kemuyi_stats";

function loadSm2(){
  try { return JSON.parse(localStorage.getItem(LS_SM2) || "{}"); }
  catch(e){ return {}; }
}
function saveSm2(sm2){
  try { localStorage.setItem(LS_SM2, JSON.stringify(sm2)); } catch(e){}
}
function loadStats(){
  try {
    var s = JSON.parse(localStorage.getItem(LS_STATS) || "null");
    if(!s) return {totalAnswered:0, totalCorrect:0, examHistory:[], lastStudyDay:0, studyDays:{}};
    if(!s.examHistory) s.examHistory = [];
    if(!s.studyDays) s.studyDays = {};
    return s;
  } catch(e){ return {totalAnswered:0, totalCorrect:0, examHistory:[], lastStudyDay:0, studyDays:{}}; }
}
function saveStats(s){
  try { localStorage.setItem(LS_STATS, JSON.stringify(s)); } catch(e){}
}

function todayStr(){
  var d = new Date();
  return d.getFullYear()+"-"+("0"+(d.getMonth()+1)).slice(-2)+"-"+("0"+d.getDate()).slice(-2);
}

/* ============================================================
 * SM-2 间隔重复算法
 * ============================================================ */
function sm2New(){
  return {ease:2.5, interval:0, reps:0, due:0, last:0};
}
// 答题后更新：quality=1答对 / 0答错
function sm2Update(card, quality, now){
  now = now || Date.now();
  if(quality >= 1){
    // 答对
    card.reps += 1;
    if(card.reps === 1) card.interval = 1;
    else if(card.reps === 2) card.interval = 3;
    else card.interval = Math.round(card.interval * card.ease);
    // ease 微增（quality=1 → +0.1）
    card.ease = card.ease + (0.1);
  } else {
    // 答错：重置 reps，间隔设1天，ease 降低
    card.reps = 0;
    card.interval = 1;
    card.ease = Math.max(1.3, card.ease - 0.2);
  }
  card.last = now;
  card.due = now + card.interval * DAY_MS;
  return card;
}
// 判断是否到期（今日该复习）：到期时间在"明天0点"之前
function sm2IsDue(card, now){
  now = now || Date.now();
  if(!card.due) return false;
  var d = new Date(now);
  var tomorrow0 = new Date(d.getFullYear(), d.getMonth(), d.getDate()+1).getTime();
  return card.due <= tomorrow0;
}
// 是否已掌握：连续答对≥3次 且 间隔≥7天
function sm2IsMastered(card){
  return card.reps >= 3 && card.interval >= 7;
}

/* 抽题：刷题模式 SM-2 智能抽题 */
function buildPracticePaper(size){
  size = size || 100;
  var now = Date.now();
  var sm2 = loadSm2();
  var ids = Object.keys(sm2);
  // 1. 到期池：SM-2 中到期题
  var duePool = [];
  var learnedPool = []; // 已学但未到期
  ids.forEach(function(id){
    var c = sm2[id];
    if(!c) return;
    if(sm2IsDue(c, now)) duePool.push(id);
    else learnedPool.push(id);
  });
  // 2. 新题池：未学过的
  var newPool = [];
  BANK.forEach(function(q){ if(!sm2[q.id]) newPool.push(q.id); });

  duePool = shuffle(duePool);
  newPool = shuffle(newPool);
  learnedPool = shuffle(learnedPool);

  var result = [];
  // 到期题最多占 size*0.7
  var dueQuota = Math.min(duePool.length, Math.round(size * 0.7));
  for(var i=0;i<dueQuota;i++) result.push(duePool[i]);
  // 新题占 size - dueQuota
  var newQuota = Math.min(newPool.length, size - result.length);
  for(var j=0;j<newQuota;j++) result.push(newPool[j]);
  // 补足：从已学未到期、再到新题、再到到期剩余中补
  if(result.length < size){
    for(var k=0;k<learnedPool.length && result.length<size;k++) result.push(learnedPool[k]);
  }
  if(result.length < size){
    for(var m=newQuota;m<newPool.length && result.length<size;m++) result.push(newPool[m]);
  }
  if(result.length < size){
    for(var n=dueQuota;n<duePool.length && result.length<size;n++) result.push(duePool[n]);
  }
  // 转 id → 题对象，去重，打乱
  var seen = {};
  var paper = [];
  result.forEach(function(id){
    if(seen[id]) return;
    seen[id] = 1;
    if(BANK_BY_ID[id]) paper.push(BANK_BY_ID[id]);
  });
  return shuffle(paper).slice(0, size);
}

/* 抽题：错题重练 = SM-2 到期题 */
function buildWrongPaper(size){
  size = size || 100;
  var now = Date.now();
  var sm2 = loadSm2();
  var dueIds = [];
  Object.keys(sm2).forEach(function(id){
    if(sm2IsDue(sm2[id], now)) dueIds.push(id);
  });
  var paper = [];
  shuffle(dueIds).forEach(function(id){
    if(BANK_BY_ID[id]) paper.push(BANK_BY_ID[id]);
  });
  return paper.slice(0, size);
}

/* 抽题：模拟考试 = 章节分层抽样（纯随机，不用SM-2） */
var byType = {judge:[], single:[]};
BANK.forEach(function(q){ (byType[q.type]||[]).push(q); });
function groupByCat(arr){
  var g={}; CATS.forEach(function(c){g[c]=[];});
  arr.forEach(function(q){ if(g[q.category]) g[q.category].push(q); });
  return g;
}
function buildExamPaper(){
  var quota = {
    judge:   {law:12, signal:10, safety:8, operation:6, case:4},
    single:  {law:18, signal:15, safety:12, operation:9, case:6}
  };
  var paper=[], used={};
  function pick(pool, n){
    var avail = pool.filter(function(q){return !used[q.id];});
    avail = shuffle(avail);
    var got=[];
    for(var k=0;k<avail.length && got.length<n;k++){ used[avail[k].id]=1; got.push(avail[k]); }
    return got;
  }
  ["judge","single"].forEach(function(type){
    var grouped = groupByCat(byType[type]);
    var q = quota[type];
    var deficit = 0;
    CATS.forEach(function(cat){
      var want = q[cat];
      var got = pick(grouped[cat], want);
      paper.push.apply(paper, got);
      deficit += (want - got.length);
    });
    if(deficit>0){
      var rest = pick(byType[type], deficit);
      paper.push.apply(paper, rest);
    }
  });
  return shuffle(paper);
}

/* ============================================================
 * 状态
 * ============================================================ */
var MODE = {PRACTICE:"practice", EXAM:"exam", WRONG:"wrong"};
var state = {
  mode: null,
  paper: [],
  idx: 0,
  answers: {},      // {idx: selectedOptionIndex}
  judged: {},       // {idx: true/false} 刷题/错题模式即时判定
  marks: {},
  startTime: 0,
  timerH: null,
  submitted: false
};

function resetState(){
  if(state.timerH){ clearInterval(state.timerH); state.timerH = null; }
  state = {mode:null, paper:[], idx:0, answers:{}, judged:{}, marks:{}, startTime:0, timerH:null, submitted:false};
}

/* ============================================================
 * 封面页
 * ============================================================ */
function refreshCover(){
  var sm2 = loadSm2();
  var stats = loadStats();
  var learnedCount = Object.keys(sm2).length;
  var masteredCount = 0;
  var dueCount = 0;
  var now = Date.now();
  Object.keys(sm2).forEach(function(id){
    var c = sm2[id];
    if(sm2IsMastered(c)) masteredCount++;
    if(sm2IsDue(c, now)) dueCount++;
  });

  $("cv-bank").textContent = BANK.length;
  $("cv-mastered").textContent = masteredCount;
  $("cv-accuracy").textContent = stats.totalAnswered > 0
    ? Math.round(stats.totalCorrect / stats.totalAnswered * 100) + "%"
    : "—";

  // 学习进度（按已学题数）
  var pct = BANK.length > 0 ? Math.round(learnedCount / BANK.length * 100) : 0;
  $("cv-progress-fill").style.width = pct + "%";
  $("cv-progress-pct").textContent = pct + "%";
  $("cv-progress-meta").textContent = "已学 " + learnedCount + " / " + BANK.length + " 题 · 掌握 " + masteredCount + " 题";

  // 错题重练按钮
  var wrongBtn = $("btn-wrong");
  if(dueCount > 0){
    wrongBtn.classList.remove("disabled");
    $("wrong-badge").textContent = dueCount;
    $("wrong-desc").textContent = "今日待复习 " + dueCount + " 题";
  } else {
    wrongBtn.classList.add("disabled");
    $("wrong-badge").textContent = learnedCount > 0 ? "0" : "—";
    $("wrong-desc").textContent = learnedCount > 0 ? "暂无待复习题" : "暂无错题记录";
  }

  // 连续学习天数
  var today = todayStr();
  $("cv-streak").textContent = (stats.studyDays[today] !== undefined || stats.lastStudyDay === today)
    ? calcStreak(stats) + "天" : (calcStreak(stats) + "天");
}

function calcStreak(stats){
  if(!stats.studyDays || Object.keys(stats.studyDays).length === 0) return 0;
  var days = Object.keys(stats.studyDays).sort();
  var streak = 0;
  var d = new Date();
  // 如果今天没学，从昨天开始算
  var todayKey = todayStr();
  if(!stats.studyDays[todayKey]){
    d.setDate(d.getDate()-1);
  }
  while(true){
    var key = d.getFullYear()+"-"+("0"+(d.getMonth()+1)).slice(-2)+"-"+("0"+d.getDate()).slice(-2);
    if(stats.studyDays[key]) { streak++; d.setDate(d.getDate()-1); }
    else break;
  }
  return streak;
}

function recordStudyDay(){
  var stats = loadStats();
  var t = todayStr();
  stats.studyDays[t] = 1;
  stats.lastStudyDay = t;
  saveStats(stats);
}

$("btn-practice").onclick = function(){ startPractice(); };
$("btn-exam").onclick = function(){ startExam(); };
$("btn-wrong").onclick = function(){
  if($("btn-wrong").classList.contains("disabled")) return;
  startWrong();
};
$("btn-reset").onclick = function(){
  if(!confirm("确定重置全部学习进度吗？\n\n将清除：SM-2 间隔记录、答题统计、模考历史。\n（图片缓存不受影响）")) return;
  localStorage.removeItem(LS_SM2);
  localStorage.removeItem(LS_STATS);
  refreshCover();
  alert("已重置学习进度。");
};

/* ============================================================
 * 开始各模式
 * ============================================================ */
function startPractice(){
  resetState();
  state.mode = MODE.PRACTICE;
  state.paper = buildPracticePaper(100);
  if(state.paper.length === 0){
    alert("题库为空，无法开始。");
    return;
  }
  enterExamPage();
}
function startWrong(){
  resetState();
  state.mode = MODE.WRONG;
  state.paper = buildWrongPaper(100);
  if(state.paper.length === 0){
    alert("暂无到期错题。");
    return;
  }
  enterExamPage();
}
function startExam(){
  resetState();
  state.mode = MODE.EXAM;
  state.paper = buildExamPaper();
  enterExamPage();
  startTimer();
}

function enterExamPage(){
  // 模式标记
  ["mb-practice","mb-exam","mb-wrong"].forEach(function(id){ $(id).classList.add("hidden"); });
  var mbId = state.mode===MODE.PRACTICE ? "mb-practice" : (state.mode===MODE.EXAM ? "mb-exam" : "mb-wrong");
  $(mbId).classList.remove("hidden");

  $("sheet").classList.remove("show"); $("sheet-mask").classList.remove("show");
  $("cur-total").textContent = state.paper.length;
  // 交卷按钮：模拟考显示在答题卡里；刷题/错题模式改为"完成练习"
  if(state.mode === MODE.EXAM){
    $("btn-submit").textContent = "交卷";
    $("btn-submit").classList.remove("hidden");
  } else {
    $("btn-submit").textContent = "完成练习";
    $("btn-submit").classList.remove("hidden");
  }
  // 模拟考显示倒计时，其它模式显示累计用时
  if(state.mode !== MODE.EXAM){
    $("timer").textContent = "0:00";
    startPracticeClock();
  }
  show("page-exam");
  renderQuestion();
  recordStudyDay();
}

/* 模拟考倒计时 45 分钟 */
function startTimer(){
  if(state.timerH){ clearInterval(state.timerH); }
  var remain = 45*60;
  function tick(){
    remain--;
    if(remain<=0){ remain=0; updateTimer(0); finishExam(true); return; }
    updateTimer(remain);
  }
  function updateTimer(s){
    var m=Math.floor(s/60), sec=s%60;
    $("timer").textContent = m+":"+ (sec<10?"0":"") +sec;
    $("timer").classList.toggle("warn", s<=300);
  }
  updateTimer(remain);
  state.timerH = setInterval(tick, 1000);
}
/* 刷题/错题模式：正向计时 */
function startPracticeClock(){
  if(state.timerH){ clearInterval(state.timerH); }
  var elapsed = 0;
  state.startTime = state.startTime || Date.now();
  function tick(){
    elapsed = Math.floor((Date.now() - state.startTime)/1000);
    var m=Math.floor(elapsed/60), sec=elapsed%60;
    $("timer").textContent = m+":"+ (sec<10?"0":"") +sec;
  }
  tick();
  state.timerH = setInterval(tick, 1000);
}

/* ============================================================
 * 渲染题目
 * ============================================================ */
function renderQuestion(){
  try {
    var i = state.idx, q = state.paper[i];
    var total = state.paper.length;
    if(!q){ $("q-area").innerHTML = '<p style="text-align:center;color:var(--gray-5)">暂无题目</p>'; return; }

    $("pg-bar").style.width = ((i+1)/total*100)+"%";
    $("cur-no").textContent = i+1;
    var done = Object.keys(state.answers).length;
    $("cur-done").textContent = done;
    $("btn-mark").classList.toggle("active", !!state.marks[i]);
    $("btn-mark").textContent = state.marks[i] ? "🚩 已标记" : "🚩 标记";
    $("btn-prev").disabled = (i===0);
    if(state.mode === MODE.EXAM){
      $("btn-next").textContent = (i===total-1) ? "查看答题卡" : "下一题 ›";
    } else {
      // 刷题/错题模式：未答题时禁用下一题，引导先答题
      $("btn-next").textContent = (i===total-1) ? "完成 ›" : "下一题 ›";
      $("btn-next").disabled = (state.judged[i] === undefined);
    }

    var tagClass = q.type==="judge"?"judge":"";
    var tagText = q.type==="judge"?"判断题":"单选题";
    var imgHtml = q.image ? ('<img class="q-image" src="'+imgUrl(q.image)+'" alt="题目图" loading="lazy" onerror="this.style.display=\'none\'">') : "";

    // 选项渲染
    var selected = state.answers[i];
    var judged = state.judged[i];
    var isPracticeLike = (state.mode !== MODE.EXAM);
    var optsHtml = q.options.map(function(o, idx){
      var cls = "opt";
      var lock = isPracticeLike && judged !== undefined; // 已判定锁定
      if(judged !== undefined){
        // 已判定（仅刷题/错题模式）
        if(idx === q.answer) cls += " correct";
        else if(idx === selected && judged === false) cls += " wrong";
        if(lock) cls += " disabled";
      } else if(selected === idx){
        cls += " selected";
      }
      return '<button class="'+cls+'" data-i="'+idx+'"><span class="k">'+String.fromCharCode(65+idx)+'</span><span>'+escapeHtml(o)+'</span></button>';
    }).join("");

    // 反馈卡片（刷题/错题模式且已答）
    var feedbackHtml = "";
    if(isPracticeLike && judged !== undefined){
      feedbackHtml = buildFeedbackHtml(q, selected, judged);
    }

    $("q-area").innerHTML =
      '<div class="q-tag '+tagClass+'">'+tagText+'</div>'+
      '<div class="q-no">第 <b>'+(i+1)+'</b> 题 / '+total+'</div>'+
      '<div class="q-text">'+escapeHtml(q.question)+'</div>'+
      imgHtml+
      '<div class="opts">'+optsHtml+'</div>'+
      feedbackHtml;

    // 绑定选项点击
    var optEls = $("q-area").querySelectorAll(".opt");
    each(optEls, function(el){
      el.onclick = function(){
        if(state.submitted) return;
        var idx = parseInt(el.getAttribute("data-i"), 10);
        onOptionClick(idx);
      };
    });
  } catch(err){
    $("q-area").innerHTML = '<p style="color:var(--red)">题目渲染异常：'+escapeHtml(err.message)+'</p>';
    if(window.console) console.error(err);
  }
}

function buildFeedbackHtml(q, selected, judged){
  var h = '<div class="feedback '+(judged?"right":"wrong")+'">';
  h += '<div class="fb-title">'+(judged?"✔ 答对了":"✘ 答错了")+'</div>';
  if(!judged){
    h += '<div class="ans-line">你的答案：<span class="your wrong">'+escapeHtml(q.options[selected])+'</span></div>';
  }
  h += '<div class="ans-line">正确答案：<span class="correct">'+escapeHtml(q.options[q.answer])+'</span></div>';
  if(q.explain){
    h += '<div class="exp"><b>解析：</b>'+escapeHtml(q.explain);
    if(q.updated) h += '<span class="updated">已按2025新规更新</span>';
    h += '</div>';
  }
  if(q.law){
    h += '<div class="exp law"><b>依据：</b>'+escapeHtml(q.law)+'</div>';
  }
  h += '</div>';
  return h;
}

/* 选项点击：分模式处理 */
function onOptionClick(idx){
  var i = state.idx;
  var q = state.paper[i];

  if(state.mode === MODE.EXAM){
    // 模拟考：可改、可取消（点已选项=取消）
    if(state.answers[i] === idx){
      delete state.answers[i];
    } else {
      state.answers[i] = idx;
    }
    renderQuestion();
    return;
  }

  // 刷题/错题模式：已判定则锁定
  if(state.judged[i] !== undefined) return;
  state.answers[i] = idx;
  var isRight = (idx === q.answer);
  state.judged[i] = isRight;

  // 更新 SM-2 与统计
  applySm2ForQuestion(q, isRight);
  updateStats(isRight);

  renderQuestion();
  renderSheet(); // 同步答题卡状态
}

/* 记录 SM-2 */
function applySm2ForQuestion(q, isRight){
  var sm2 = loadSm2();
  var card = sm2[q.id] || sm2New();
  sm2Update(card, isRight ? 1 : 0);
  sm2[q.id] = card;
  saveSm2(sm2);
}
function updateStats(isRight){
  var stats = loadStats();
  stats.totalAnswered += 1;
  if(isRight) stats.totalCorrect += 1;
  saveStats(stats);
}

/* ============================================================
 * 导航
 * ============================================================ */
$("btn-prev").onclick = function(){
  if(state.idx > 0){ state.idx--; renderQuestion(); window.scrollTo(0,0); }
};
$("btn-next").onclick = function(){
  if(state.mode !== MODE.EXAM && state.judged[state.idx] === undefined){
    // 刷题模式：未答不能跳（但允许通过答题卡跳转）
    return;
  }
  if(state.idx < state.paper.length - 1){
    state.idx++; renderQuestion(); window.scrollTo(0,0);
  } else {
    // 最后一题
    if(state.mode === MODE.EXAM){
      openSheet();
    } else {
      // 刷题/错题模式完成
      finishPractice();
    }
  }
};
$("btn-mark").onclick = function(){
  var i = state.idx;
  if(state.marks[i]) delete state.marks[i]; else state.marks[i] = 1;
  renderQuestion();
};

/* ============================================================
 * 答题卡
 * ============================================================ */
$("btn-sheet").onclick = openSheet;
$("sheet-mask").onclick = closeSheet;
$("sheet-close").onclick = closeSheet;
function openSheet(){
  renderSheet();
  $("sheet").classList.add("show"); $("sheet-mask").classList.add("show");
}
function closeSheet(){ $("sheet").classList.remove("show"); $("sheet-mask").classList.remove("show"); }
function renderSheet(){
  // 图例：模拟考用已答，刷题/错题用对错
  var legend = $("sheet-legend");
  if(state.mode === MODE.EXAM){
    legend.innerHTML =
      '<span><i style="background:var(--blue);border-color:var(--blue)"></i>已答</span>'+
      '<span><i></i>未答</span>'+
      '<span><i style="border-color:var(--orange)"></i>标记</span>';
  } else {
    legend.innerHTML =
      '<span><i style="background:var(--green);border-color:var(--green)"></i>答对</span>'+
      '<span><i style="background:var(--red);border-color:var(--red)"></i>答错</span>'+
      '<span><i></i>未答</span>'+
      '<span><i style="border-color:var(--orange)"></i>标记</span>';
  }

  var html="";
  state.paper.forEach(function(q, i){
    var cls="";
    if(state.mode === MODE.EXAM){
      if(state.answers[i] !== undefined) cls += " answered";
    } else {
      if(state.judged[i] === true) cls += " right";
      else if(state.judged[i] === false) cls += " wrong";
    }
    if(state.marks[i]) cls += " marked";
    if(i === state.idx) cls += " current";
    html += '<button class="'+cls.trim()+'" data-i="'+i+'">'+(i+1)+'</button>';
  });
  $("sheet-grid").innerHTML = html;
  each($("sheet-grid").children, function(b){
    b.onclick = function(){
      state.idx = parseInt(b.getAttribute("data-i"), 10);
      closeSheet();
      renderQuestion();
      window.scrollTo(0,0);
    };
  });
}

/* 交卷/完成按钮 */
$("btn-submit").onclick = function(){
  if(state.mode === MODE.EXAM){
    var unanswered = state.paper.length - Object.keys(state.answers).length;
    if(unanswered > 0){
      if(!confirm("还有 "+unanswered+" 题未作答，确定交卷吗？")) return;
    } else {
      if(!confirm("确定交卷吗？")) return;
    }
    finishExam(false);
  } else {
    // 刷题/错题模式：完成练习
    var done = Object.keys(state.judged).length;
    var total = state.paper.length;
    if(done < total){
      if(!confirm("还有 "+(total-done)+" 题未做，提前结束本次练习吗？")) return;
    } else {
      if(!confirm("已完成全部题目，查看本次练习总结？")) return;
    }
    finishPractice();
  }
};

/* ============================================================
 * 结束：刷题/错题模式总结
 * ============================================================ */
function finishPractice(){
  if(state.timerH){ clearInterval(state.timerH); state.timerH = null; }
  state.submitted = true;
  closeSheet();

  var paper = state.paper;
  var right = 0, wrong = 0;
  paper.forEach(function(q, i){
    if(state.judged[i] === true) right++;
    else if(state.judged[i] === false) wrong++;
  });
  var done = right + wrong;
  var total = paper.length;
  var usedMin = Math.round((Date.now() - state.startTime)/60000);
  var acc = done > 0 ? Math.round(right/done*100) : 0;
  var pass = acc >= 90;

  // 分数环
  $("r-score").textContent = acc;
  var C = 2*Math.PI*70, pct = acc/100;
  var arc = $("score-arc");
  arc.setAttribute("stroke-dasharray", (C*pct)+" "+C);
  arc.setAttribute("stroke", pass ? "#07c160" : "#fa5151");

  var title = state.mode === MODE.WRONG ? "错题重练完成" : "本次练习完成";
  $("r-verdict").textContent = title;
  $("r-verdict").className = "verdict " + (pass ? "pass" : "fail");
  $("r-verdict-sub").textContent = "答对 "+right+" / "+done+" 题 · 正确率 "+acc+"% · 用时 "+usedMin+"′";
  $("r-right").textContent = right;
  $("r-wrong").textContent = wrong;
  $("r-time").textContent = usedMin + "′";

  // 再考一次按钮：错题重练→返回首页（重新进会有新到期题），刷题→继续刷题
  $("btn-again").textContent = "再来一轮";
  $("btn-again").onclick = function(){
    if(state.mode === MODE.WRONG) startWrong();
    else startPractice();
  };

  // 解析回顾（仅错题，可筛选）
  renderReview(paper, state.judged, state.answers, true);
  show("page-result");
}

/* ============================================================
 * 结束：模拟考判定
 * ============================================================ */
function finishExam(timeout){
  if(state.submitted) return;
  state.submitted = true;
  if(state.timerH){ clearInterval(state.timerH); state.timerH = null; }
  closeSheet();
  showExamResult(timeout);
}

function showExamResult(timeout){
  var paper = state.paper, right = 0, wrongList = [];
  // 判分（健壮 for 循环）
  for(var i=0;i<paper.length;i++){
    if(state.answers[i] === paper[i].answer) right++;
    else wrongList.push(i);
  }
  var wrong = paper.length - right;
  var score = right;
  var pass = score >= 90;
  var usedMin = Math.round((Date.now() - state.startTime)/60000);

  // 把模考答错的题注入 SM-2 队列（interval=1，明日到期）
  var sm2 = loadSm2();
  wrongList.forEach(function(i){
    var q = paper[i];
    var card = sm2[q.id] || sm2New();
    // 无论原状态，答错置为待复习
    card.reps = 0;
    card.interval = 1;
    card.ease = Math.max(1.3, card.ease - 0.2);
    card.last = Date.now();
    card.due = Date.now() + DAY_MS;
    sm2[q.id] = card;
  });
  saveSm2(sm2);

  // 记录模考历史
  var stats = loadStats();
  stats.examHistory.push({score:score, right:right, wrong:wrong, time:usedMin, date:Date.now(), timeout:!!timeout});
  if(stats.examHistory.length > 50) stats.examHistory = stats.examHistory.slice(-50);
  saveStats(stats);

  $("r-score").textContent = score;
  $("r-right").textContent = right;
  $("r-wrong").textContent = wrong;
  $("r-time").textContent = usedMin + "′";
  $("r-verdict").textContent = timeout ? "考试时间到" : (pass ? "恭喜，考试合格！" : "很遗憾，未合格");
  $("r-verdict").className = "verdict " + (pass ? "pass" : "fail");
  $("r-verdict-sub").textContent = pass
    ? "（合格线 90 分，你答对 "+right+" 题）"
    : "（合格线 90 分，还需再对 "+(90-score)+" 题）";

  var C = 2*Math.PI*70, pct = score/100;
  var arc = $("score-arc");
  arc.setAttribute("stroke-dasharray", (C*pct)+" "+C);
  arc.setAttribute("stroke", pass ? "#07c160" : "#fa5151");

  $("btn-again").textContent = "再考一次";
  $("btn-again").onclick = startExam;

  // 逐题解析
  renderReview(paper, judgeMapFromAnswers(paper, state.answers), state.answers, false);
  show("page-result");
}

function judgeMapFromAnswers(paper, answers){
  var m = {};
  for(var i=0;i<paper.length;i++){
    if(answers[i] !== undefined){
      m[i] = (answers[i] === paper[i].answer);
    }
  }
  return m;
}

/* ============================================================
 * 结果页解析回顾（带筛选）
 * ============================================================ */
var _reviewState = {paper:[], judged:{}, answers:{}, filter:"all"};
function renderReview(paper, judged, answers, practiceMode){
  _reviewState = {paper:paper, judged:judged, answers:answers, filter:"all"};
  var wrong = 0;
  paper.forEach(function(q,i){ if(judged[i]===false) wrong++; });

  var reviewEl = $("review");
  reviewEl.innerHTML = '<h3>📋 逐题解析'+(wrong>0?'（错题已置顶）':'')+'</h3>';

  // 筛选器（有错题时显示）
  var filterEl = $("rv-filter");
  if(wrong > 0){
    filterEl.classList.remove("hidden");
    each(filterEl.querySelectorAll("button"), function(b){
      b.classList.toggle("active", b.getAttribute("data-f") === "all");
      b.onclick = function(){
        _reviewState.filter = b.getAttribute("data-f");
        each(filterEl.querySelectorAll("button"), function(x){ x.classList.remove("active"); });
        b.classList.add("active");
        renderReviewList();
      };
    });
  } else {
    filterEl.classList.add("hidden");
  }

  renderReviewList();
}

function renderReviewList(){
  var paper = _reviewState.paper, judged = _reviewState.judged, answers = _reviewState.answers;
  var filter = _reviewState.filter;
  // 排序：错题置顶
  var wrongIdx = [], rightIdx = [], noIdx = [];
  for(var i=0;i<paper.length;i++){
    if(judged[i]===false) wrongIdx.push(i);
    else if(judged[i]===true) rightIdx.push(i);
    else noIdx.push(i);
  }
  var order = wrongIdx.concat(noIdx).concat(rightIdx);
  if(filter === "wrong") order = wrongIdx;

  var html = "";
  for(var k=0;k<order.length;k++){
    var i = order[k];
    var q = paper[i], your = answers[i], correct = q.answer, isRight = (judged[i]===true);
    var isWrong = (judged[i]===false);
    var cardCls = isRight ? "right" : (isWrong ? "wrong" : "");
    html += '<div class="rv-item '+cardCls+'">';
    var label = isRight ? "✔ 答对" : (isWrong ? "✘ 答错" : "— 未答");
    var labelCls = isRight ? "right" : (isWrong ? "wrong" : "");
    html += '<div class="rv-head"><span class="t '+labelCls+'">'+label+'</span><span class="t">第'+(i+1)+'题 · '+(q.type==="judge"?"判断":"单选")+'</span></div>';
    html += '<div class="rv-q">'+escapeHtml(q.question);
    if(q.image) html += '<br><img src="'+imgUrl(q.image)+'" alt="" loading="lazy" onerror="this.style.display=\'none\'">';
    html += '</div>';
    if(isWrong && your !== undefined){
      html += '<div class="rv-ans">你的答案：<span class="your wrong">'+escapeHtml(q.options[your])+'</span></div>';
    } else if(your === undefined){
      html += '<div class="rv-ans"><span style="color:var(--gray-5)">（未作答）</span></div>';
    }
    html += '<div class="rv-ans">正确答案：<span class="correct">'+escapeHtml(q.options[correct])+'</span></div>';
    if(q.explain) html += '<div class="rv-exp"><b>解析：</b>'+escapeHtml(q.explain)+(q.updated?'<span class="rv-updated">已按2025新规更新</span>':'')+'</div>';
    if(q.law) html += '<div class="rv-exp" style="margin-top:4px"><b>依据：</b>'+escapeHtml(q.law)+'</div>';
    html += '</div>';
  }
  $("review").innerHTML = '<h3>📋 逐题解析'+(wrongIdxCount()>0?'（错题已置顶）':'')+'</h3>' + html;
  window.scrollTo(0,0);
}
function wrongIdxCount(){
  var c=0; for(var k in _reviewState.judged){ if(_reviewState.judged[k]===false) c++; } return c;
}

$("btn-result-home").onclick = function(){
  resetState();
  refreshCover();
  show("page-cover");
};

/* ============================================================
 * 图片预下载 (Cache API)
 * ============================================================ */
var _dlCancelled = false;
$("btn-predl").onclick = function(){ openPredl(); };

function openPredl(){
  var urls = [];
  BANK.forEach(function(q){ if(q.image) urls.push(imgUrl(q.image)); });
  if(urls.length === 0){ alert("题库无图片。"); return; }
  $("dl-title").textContent = "📥 预下载图片库";
  $("dl-sub").textContent = "将下载全部 "+urls.length+" 张题目图片至本地，支持离线查看。预计约 50-100MB。";
  $("dl-fill").style.width = "0%";
  $("dl-num").textContent = "点击开始下载";
  $("dl-cancel").textContent = "开始下载";
  $("dl-mask").classList.add("show");

  var started = false;
  $("dl-cancel").onclick = function(){
    if(!started){
      // 开始
      started = true;
      _dlCancelled = false;
      $("dl-cancel").textContent = "取消";
      runPredl(urls);
    } else {
      _dlCancelled = true;
    }
  };
}

async function runPredl(urls){
  if(!("caches" in window)){ $("dl-num").textContent = "浏览器不支持缓存"; return; }
  var cache = await caches.open("kemuyi-imgs");
  var done = 0, failed = 0;
  for(var i=0;i<urls.length;i++){
    if(_dlCancelled){
      $("dl-num").textContent = "已取消（"+done+"/"+urls.length+"）";
      $("dl-cancel").textContent = "关闭";
      $("dl-cancel").onclick = function(){ $("dl-mask").classList.remove("show"); refreshCover(); };
      return;
    }
    try {
      var cached = await cache.match(urls[i]);
      if(!cached){
        var resp = await fetch(urls[i], {mode:"no-cors"});
        if(resp.ok || resp.type === "opaque") await cache.put(urls[i], resp);
      }
      done++;
    } catch(e){ failed++; done++; }
    // 进度（每3张更新一次UI，避免频繁重绘）
    if(i % 3 === 0 || i === urls.length-1){
      $("dl-fill").style.width = Math.round(done/urls.length*100)+"%";
      $("dl-num").textContent = done+" / "+urls.length + (failed>0 ? "（失败 "+failed+"）" : "");
    }
  }
  $("dl-title").textContent = "✅ 下载完成";
  $("dl-sub").textContent = "图片库已离线可用"+(failed>0 ? "（"+failed+"张下载失败，可稍后重试）" : "");
  $("dl-num").textContent = done + " / " + urls.length;
  $("dl-cancel").textContent = "完成";
  $("dl-cancel").onclick = function(){ $("dl-mask").classList.remove("show"); refreshCover(); };
}

/* ============================================================
 * Service Worker 注册
 * ============================================================ */
if("serviceWorker" in navigator){
  window.addEventListener("load", function(){
    navigator.serviceWorker.register("sw.js").then(function(reg){
      // 注册成功
    }).catch(function(e){
      // file:// 或不支持时静默失败
      if(window.console) console.warn("SW 注册失败:", e);
    });
  });
}

/* ============================================================
 * 启动
 * ============================================================ */
refreshCover();
show("page-cover");

})();
</script>
</body>
</html>
"""


def main():
    with open(BANK, encoding="utf-8") as f:
        bank = json.load(f)

    # 紧凑 JSON，减少体积
    bank_json = json.dumps(bank, ensure_ascii=False, separators=(",", ":"))

    # 先替换版本号占位符（模板自身），再内联题库
    # 顺序重要：避免题库文本万一含占位符串被误替换
    html = TEMPLATE.replace("__BUILD_VER__", BUILD_VER).replace("__BANK_JSON__", bank_json)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    # manifest.json
    manifest = {
        "name": "C1 驾照 · 科目一模拟考试",
        "short_name": "科目一",
        "description": "智能刷题 + 模拟考试，SM-2 间隔重复算法精选，离线可用",
        "start_url": ".",
        "scope": ".",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#f7f8fa",
        "theme_color": "#1e80ff",
        "lang": "zh-CN",
        "icons": [
            {"src": "icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}
        ]
    }
    with open(OUT_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # sw.js
    sw_js = SW_TEMPLATE.replace("__BUILD_VER__", BUILD_VER)
    with open(OUT_SW, "w", encoding="utf-8") as f:
        f.write(sw_js)

    # PWA 图标（用 Pillow 生成；无 Pillow 时跳过，保留已存在的图标）
    try:
        generate_icons()
    except ImportError:
        print("提示: 未安装 Pillow，跳过图标生成（保留现有图标文件）")

    size_kb = os.path.getsize(OUT_HTML) / 1024
    print(f"已生成: {OUT_HTML}")
    print(f"  题库: {len(bank)} 题")
    print(f"  体积: {size_kb:.1f} KB ({size_kb/1024:.2f} MB)")
    print(f"已生成: {OUT_MANIFEST}")
    print(f"已生成: {OUT_SW}  (缓存版本: {BUILD_VER})")
    print(f"构建版本: {BUILD_VER}")


def generate_icons():
    """用 Pillow 生成 PWA 图标：蓝紫渐变背景 + 白色简化汽车。"""
    from PIL import Image, ImageDraw

    BLUE = (30, 128, 255)
    BLUE_DARK = (22, 96, 216)
    WHITE = (255, 255, 255)

    def lerp(a, b, t):
        return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

    def make_icon(size, path):
        S = size * 4  # 超采样抗锯齿
        img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        # 背景填满纯色（maskable 安全区）
        img.paste(BLUE, (0, 0, S, S))
        # 渐变叠加
        grad = Image.new("RGBA", (S, S))
        gp = grad.load()
        for y in range(S):
            for x in range(S):
                t = (x + y) / (2 * S)
                gp[x, y] = lerp(BLUE, BLUE_DARK, t) + (255,)
        img = Image.alpha_composite(img, grad)
        draw = ImageDraw.Draw(img)

        cx, cy = S / 2, S / 2
        w = S * 0.56
        h = S * 0.38
        left = cx - w / 2
        right = cx + w / 2
        top = cy - h / 2
        bottom = cy + h / 2
        body_top = top + h * 0.28

        # 车身
        draw.rounded_rectangle([left, body_top, right, bottom], radius=h * 0.18, fill=WHITE)
        # 驾驶舱
        cabin_l, cabin_r = left + w * 0.20, right - w * 0.20
        draw.polygon([
            (cabin_l + w * 0.06, body_top), (cabin_r - w * 0.06, body_top),
            (cabin_r - w * 0.16, top + h * 0.02), (cabin_l + w * 0.16, top + h * 0.02)
        ], fill=WHITE)
        # 车窗
        draw.polygon([
            (cabin_l + w * 0.15, body_top - S * 0.005), (cabin_r - w * 0.15, body_top - S * 0.005),
            (cabin_r - w * 0.19, top + h * 0.05), (cabin_l + w * 0.19, top + h * 0.05)
        ], fill=BLUE_DARK)
        # 车轮
        wheel_r = w * 0.10
        wheel_y = bottom - S * 0.005
        for wx in (left + w * 0.24, right - w * 0.24):
            draw.ellipse([wx - wheel_r, wheel_y - wheel_r * 0.7, wx + wheel_r, wheel_y + wheel_r * 0.7], fill=BLUE_DARK)
            hub_r = wheel_r * 0.4
            draw.ellipse([wx - hub_r, wheel_y - hub_r * 0.7, wx + hub_r, wheel_y + hub_r * 0.7], fill=WHITE)

        img.resize((size, size), Image.LANCZOS).save(path, "PNG")

    make_icon(192, OUT_ICON_192)
    make_icon(512, OUT_ICON_512)
    make_icon(32, OUT_FAVICON)
    print(f"已生成: icon-192.png / icon-512.png / favicon.png")


# Service Worker 模板
SW_TEMPLATE = r"""// Service Worker — 科目一 PWA
// 缓存版本随构建注入，更新时自动清理旧缓存
var CACHE_VER = "kemuyi-__BUILD_VER__";
var SHELL_CACHE = CACHE_VER + "-shell";
var IMG_CACHE = "kemuyi-imgs";

// 预缓存的应用壳文件
var SHELL_FILES = [
  "./",
  "./index.html",
  "./manifest.json",
  "./icon-192.png",
  "./icon-512.png"
];

self.addEventListener("install", function(e){
  e.waitUntil(
    caches.open(SHELL_CACHE).then(function(cache){
      // 逐个缓存，单文件失败不阻塞
      return Promise.all(SHELL_FILES.map(function(url){
        return cache.add(url).catch(function(){ /* 忽略单文件失败 */ });
      }));
    }).then(function(){
      return self.skipWaiting();
    })
  );
});

self.addEventListener("activate", function(e){
  e.waitUntil(
    caches.keys().then(function(keys){
      return Promise.all(keys.map(function(key){
        // 清理旧版本 shell 缓存（保留图片缓存 kemuyi-imgs）
        if(key.indexOf("kemuyi-") === 0 && key !== SHELL_CACHE && key !== IMG_CACHE){
          return caches.delete(key);
        }
      }));
    }).then(function(){
      return self.clients.claim();
    })
  );
});

self.addEventListener("fetch", function(e){
  var req = e.request;
  var url = new URL(req.url);

  // 仅处理 GET
  if(req.method !== "GET") return;

  // 图片请求：cache-first（懒缓存核心）
  var isImg = req.destination === "image" || /\.(jpg|jpeg|png|gif|webp)(\?|$)/i.test(url.pathname);
  if(isImg && url.origin !== self.location.origin){
    e.respondWith(imgCacheFirst(req));
    return;
  }

  // 同源导航/静态资源：stale-while-revalidate
  if(url.origin === self.location.origin){
    e.respondWith(shellSWR(req));
    return;
  }
  // 其他跨域请求：直接放行（不缓存）
});

function imgCacheFirst(req){
  return caches.open(IMG_CACHE).then(function(cache){
    return cache.match(req).then(function(cached){
      if(cached) return cached;
      return fetch(req).then(function(resp){
        // 缓存成功的图片响应
        if(resp && (resp.ok || resp.type === "opaque")){
          cache.put(req, resp.clone()).catch(function(){});
        }
        return resp;
      }).catch(function(){
        // 离线且无缓存：返回透明占位，避免破图
        return new Response("", {status:204});
      });
    });
  });
}

function shellSWR(req){
  return caches.open(SHELL_CACHE).then(function(cache){
    return cache.match(req).then(function(cached){
      var fetchPromise = fetch(req).then(function(resp){
        if(resp && resp.ok && (req.mode !== "navigate" || resp.type !== "opaqueredirect")){
          cache.put(req, resp.clone()).catch(function(){});
        }
        return resp;
      }).catch(function(){
        // 离线：导航请求回退到缓存的 index.html
        if(req.mode === "navigate"){
          return cache.match("./index.html").then(function(r){ return r || cached; });
        }
        return cached;
      });
      return cached || fetchPromise;
    });
  });
}

// 接收页面消息：清除图片缓存
self.addEventListener("message", function(e){
  if(e.data === "clear-img-cache"){
    caches.delete(IMG_CACHE).then(function(){
      e.source && e.source.postMessage({type:"img-cache-cleared"});
    });
  }
});
"""


if __name__ == "__main__":
    main()
