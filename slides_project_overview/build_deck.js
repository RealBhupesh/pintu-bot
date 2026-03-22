"use strict";

const fs = require("fs");
const path = require("path");
const PptxGenJS = require("pptxgenjs");
const {
  autoFontSize,
  calcTextBox,
  safeOuterShadow,
  warnIfSlideHasOverlaps,
  warnIfSlideElementsOutOfBounds,
} = require("./pptxgenjs_helpers");

const pptx = new PptxGenJS();
pptx.layout = "LAYOUT_WIDE";
pptx.author = "Codex";
pptx.company = "OpenAI";
pptx.subject = "Bell Discord Bot Project Overview";
pptx.title = "Bell Discord Bot - Project Overview";
pptx.lang = "en-US";
pptx.theme = {
  headFontFace: "Aptos Display",
  bodyFontFace: "Aptos",
  lang: "en-US",
};

const OUT_DIR = __dirname;
const OUT_FILE = path.join(OUT_DIR, "bell_project_overview.pptx");

const C = {
  ink: "102033",
  navy: "0F2747",
  blue: "1E4E8C",
  cyan: "2B7C85",
  mint: "9AD7D0",
  sand: "F2EDE3",
  fog: "F6F8FB",
  steel: "7B8AA0",
  white: "FFFFFF",
  red: "B14A42",
  amber: "D1972B",
  green: "2D7B55",
};

const FONT_HEAD = "Aptos Display";
const FONT_BODY = "Aptos";

function card(slide, x, y, w, h, fill, title, body, opts = {}) {
  slide.addShape(pptx.ShapeType.roundRect, {
    x,
    y,
    w,
    h,
    rectRadius: 0.08,
    line: { color: opts.lineColor || fill, pt: opts.linePt || 0 },
    fill: { color: fill },
    shadow: safeOuterShadow("000000", 0.14, 45, 1.5, 0.7),
  });
  slide.addText(title, {
    x: x + 0.18,
    y: y + 0.16,
    w: w - 0.36,
    h: 0.28,
    fontFace: FONT_HEAD,
    fontSize: opts.titleSize || 15,
    bold: true,
    color: opts.titleColor || C.ink,
    margin: 0,
  });
  const bodyBox = calcTextBox(opts.bodySize || 10.5, {
    text: body,
    w: w - 0.36,
    fontFace: FONT_BODY,
    margin: 0,
    padding: 0,
    leading: 1.2,
  });
  slide.addText(body, {
    x: x + 0.18,
    y: y + 0.52,
    w: w - 0.36,
    h: Math.min(h - 0.66, bodyBox.h + 0.12),
    fontFace: FONT_BODY,
    fontSize: opts.bodySize || 10.5,
    color: opts.bodyColor || C.ink,
    margin: 0,
    breakLine: false,
    valign: "top",
  });
}

function tag(slide, x, y, text, fill, color = C.white, w = 1.4) {
  slide.addShape(pptx.ShapeType.roundRect, {
    x,
    y,
    w,
    h: 0.34,
    rectRadius: 0.08,
    line: { color: fill, pt: 0 },
    fill: { color: fill },
  });
  slide.addText(text, {
    x,
    y: y + 0.03,
    w,
    h: 0.22,
    align: "center",
    margin: 0,
    fontFace: FONT_BODY,
    fontSize: 9,
    bold: true,
    color,
  });
}

function sectionTitle(slide, kicker, title, subtitle = "") {
  slide.addText(kicker.toUpperCase(), {
    x: 0.55,
    y: 0.28,
    w: 3.0,
    h: 0.2,
    fontFace: FONT_BODY,
    fontSize: 8.5,
    bold: true,
    color: C.cyan,
    charSpace: 1.2,
    margin: 0,
  });
  slide.addText(title, autoFontSize(title, FONT_HEAD, {
    x: 0.55,
    y: 0.5,
    w: 8.6,
    h: 0.6,
    fontSize: 24,
    minFontSize: 20,
    maxFontSize: 28,
    bold: true,
    color: C.navy,
    margin: 0,
    mode: "auto",
  }));
  if (subtitle) {
    slide.addText(subtitle, {
      x: 0.55,
      y: 1.1,
      w: 8.8,
      h: 0.44,
      fontFace: FONT_BODY,
      fontSize: 10.5,
      color: C.steel,
      margin: 0,
    });
  }
}

function footer(slide, num) {
  slide.addText(`Bell Discord Bot | Project Overview | ${num}`, {
    x: 0.55,
    y: 7.0,
    w: 3.5,
    h: 0.18,
    margin: 0,
    fontFace: FONT_BODY,
    fontSize: 8,
    color: C.steel,
  });
}

function background(slide) {
  slide.background = { color: C.white };
}

function metricChip(slide, x, y, value, label, fill) {
  slide.addShape(pptx.ShapeType.roundRect, {
    x,
    y,
    w: 1.75,
    h: 0.9,
    rectRadius: 0.08,
    line: { color: fill, pt: 0 },
    fill: { color: fill },
  });
  slide.addText(value, {
    x: x + 0.14,
    y: y + 0.12,
    w: 1.45,
    h: 0.28,
    margin: 0,
    fontFace: FONT_HEAD,
    fontSize: 19,
    bold: true,
    color: C.white,
    align: "center",
  });
  slide.addText(label, {
    x: x + 0.12,
    y: y + 0.48,
    w: 1.5,
    h: 0.18,
    margin: 0,
    fontFace: FONT_BODY,
    fontSize: 8.2,
    color: C.white,
    align: "center",
  });
}

function addArrow(slide, x1, y1, x2, y2, color = C.blue) {
  slide.addShape(pptx.ShapeType.line, {
    x: x1,
    y: y1,
    w: x2 - x1,
    h: y2 - y1,
    line: { color, pt: 1.5, endArrowType: "triangle" },
  });
}

function finalize(slide) {
  warnIfSlideHasOverlaps(slide, pptx);
  warnIfSlideElementsOutOfBounds(slide, pptx);
}

function build() {
  let slide;

  slide = pptx.addSlide();
  background(slide);
  slide.addShape(pptx.ShapeType.rect, {
    x: 0.55,
    y: 0.72,
    w: 0.18,
    h: 2.7,
    line: { color: C.cyan, pt: 0 },
    fill: { color: C.cyan },
  });
  slide.addText("DISCORD COMMUNITY OPERATIONS", {
    x: 0.92,
    y: 0.8,
    w: 3.2,
    h: 0.2,
    margin: 0,
    fontFace: FONT_BODY,
    fontSize: 8.5,
    bold: true,
    color: C.cyan,
    charSpace: 1.2,
  });
  slide.addText("Bell", autoFontSize("Bell", FONT_HEAD, {
    x: 0.92,
    y: 1.06,
    w: 2.2,
    h: 0.7,
    fontSize: 28,
    minFontSize: 26,
    maxFontSize: 34,
    bold: true,
    color: C.navy,
    margin: 0,
  }));
  slide.addText("Professional Project Overview", autoFontSize("Professional Project Overview", FONT_HEAD, {
    x: 0.92,
    y: 1.82,
    w: 5.8,
    h: 0.65,
    fontSize: 24,
    minFontSize: 20,
    maxFontSize: 28,
    bold: true,
    color: C.ink,
    margin: 0,
  }));
  slide.addText(
    "A multi-function Discord bot that combines moderation, AI assistance, social interaction, engagement systems, economy simulation, and music controls in a single event-driven runtime.",
    {
      x: 0.92,
      y: 2.72,
      w: 6.6,
      h: 1.1,
      fontFace: FONT_BODY,
      fontSize: 12,
      color: C.steel,
      margin: 0,
      valign: "top",
    }
  );
  tag(slide, 0.92, 4.08, "Prefix + Slash", C.navy, C.white, 1.55);
  tag(slide, 2.6, 4.08, "Natural Language", C.blue, C.white, 1.8);
  tag(slide, 4.55, 4.08, "Stateful Runtime", C.cyan, C.white, 1.7);
  metricChip(slide, 9.42, 1.05, "6", "Core product pillars", C.navy);
  metricChip(slide, 11.28, 1.05, "1", "Main runtime process", C.blue);
  metricChip(slide, 9.42, 2.13, "AI", "Guardrails and social UX", C.cyan);
  metricChip(slide, 11.28, 2.13, "JSON", "Operational state backend", C.ink);
  card(
    slide,
    9.32,
    3.35,
    3.45,
    2.15,
    C.white,
    "What this deck covers",
    "Objectives, product scope, runtime architecture, message lifecycle, AI systems, economy and engagement engines, operational problems, deployment constraints, and strategic recommendations.",
    { lineColor: "DCE3EC", linePt: 1, bodySize: 10.2 }
  );
  footer(slide, 1);
  finalize(slide);

  slide = pptx.addSlide();
  background(slide);
  sectionTitle(
    slide,
    "Executive Summary",
    "A community operations platform disguised as a Discord bot",
    "Bell has grown from a moderation utility into a broad operational layer for Discord communities."
  );
  card(slide, 0.6, 1.65, 3.85, 1.6, C.sand, "What Bell is", "An event-driven Discord bot built in Python with a large command surface, natural-language routing, scheduled loops, AI integrations, and persistent state.", { bodySize: 10.3 });
  card(slide, 0.6, 3.42, 3.85, 1.6, C.fog, "Who it serves", "Server owners, moderators, and members who need moderation, assistance, entertainment, engagement mechanics, or economy gameplay without switching tools.", { bodySize: 10.3, lineColor: "DCE3EC", linePt: 1 });
  card(slide, 0.6, 5.18, 3.85, 1.6, "EEF8F6", "Why it matters", "It centralizes multiple workflows into one bot identity, reducing context switching and creating a more interactive, sticky community experience.", { bodySize: 10.3, lineColor: "D6ECE8", linePt: 1 });
  card(slide, 4.75, 1.65, 3.85, 1.6, C.white, "Operating model", "User input enters a shared runtime pipeline: moderation checks, conversational routing, feature handlers, state updates, scheduled flush loops, and outbound responses.", { bodySize: 10.3, lineColor: "DCE3EC", linePt: 1 });
  card(slide, 4.75, 3.42, 3.85, 1.6, "E9F0F8", "Core differentiator", "The same bot supports strict moderation, playful AI features, and persistent economy gameplay in one codebase and one server identity.", { bodySize: 10.3, lineColor: "D6E3F2", linePt: 1 });
  card(slide, 8.98, 1.65, 3.65, 5.13, C.navy, "Project takeaway", "Bell is effectively a small platform. The project demonstrates command design, event orchestration, AI integration, background processing, persistence handling, and host-level operational tradeoffs.", { titleColor: C.white, bodyColor: C.white, bodySize: 11.1 });
  footer(slide, 2);
  finalize(slide);

  slide = pptx.addSlide();
  background(slide);
  sectionTitle(
    slide,
    "Objectives and Problems",
    "What the project is trying to achieve",
    "The design mixes utility, moderation, entertainment, and retention mechanics."
  );
  card(slide, 0.65, 1.75, 4.0, 4.85, C.white, "Primary objectives", "Protect the server with moderation and AI Guard.\nSupport members with utility and AI assistance.\nIncrease retention through engagement loops and social features.\nCreate a sticky economy layer through stocks, loans, and businesses.\nOffer voice and media controls through music commands.", { lineColor: "DCE3EC", linePt: 1, bodySize: 11 });
  card(slide, 4.95, 1.75, 4.0, 4.85, "EEF8F6", "Problems being addressed", "Manual moderation does not scale.\nMembers need faster answers and summaries.\nCommunities lose momentum without recurring interaction hooks.\nMost bots solve one problem area only.\nAdmins want a single operational bot instead of multiple overlapping bots.", { lineColor: "D6ECE8", linePt: 1, bodySize: 11 });
  card(slide, 9.25, 1.75, 3.4, 4.85, C.sand, "Success criteria", "Fast moderation response.\nNatural command discovery.\nVisible community engagement.\nPersistent game state.\nLow-friction hosting and recoverability.\nClear operational controls for moderators.", { lineColor: "E4D7C1", linePt: 1, bodySize: 10.9 });
  footer(slide, 3);
  finalize(slide);

  slide = pptx.addSlide();
  background(slide);
  sectionTitle(
    slide,
    "Product Scope",
    "Six major capability pillars",
    "The bot spans governance, assistance, gameplay, and media features."
  );
  card(slide, 0.65, 1.65, 2.95, 1.5, C.navy, "Moderation", "Manual actions, AutoMod, AI Guard, appeals, case management, mod logs.", { titleColor: C.white, bodyColor: C.white, bodySize: 10.1 });
  card(slide, 3.8, 1.65, 2.95, 1.5, C.blue, "AI Assistant", "AI chat, summaries, catch-up, insights, psych mode, argument and debate.", { titleColor: C.white, bodyColor: C.white, bodySize: 10.1 });
  card(slide, 6.95, 1.65, 2.95, 1.5, C.cyan, "Social AI", "Roast, vibe, aicrush, futureme, lie detector, rizzcoach, server lore.", { titleColor: C.white, bodyColor: C.white, bodySize: 10.1 });
  card(slide, 0.65, 3.45, 2.95, 1.5, C.sand, "Economy", "Cash, portfolios, commodities, crypto, loans, taxes, private businesses.", { titleColor: C.ink, bodyColor: C.ink, bodySize: 10.1 });
  card(slide, 3.8, 3.45, 2.95, 1.5, "EEF8F6", "Engagement", "XP, streaks, quests, events, catch-up nudges, onboarding and recommendations.", { titleColor: C.ink, bodyColor: C.ink, bodySize: 10.1, lineColor: "D6ECE8", linePt: 1 });
  card(slide, 6.95, 3.45, 2.95, 1.5, C.fog, "Music + Utility", "Voice join/playback, avatar, user info, server info, polls, reminders, snipe.", { titleColor: C.ink, bodyColor: C.ink, bodySize: 10.1, lineColor: "DCE3EC", linePt: 1 });
  card(slide, 10.2, 1.65, 2.45, 3.3, C.white, "Design implication", "Bell is not a narrow bot. It behaves more like a platform with multiple bounded subsystems sharing one runtime, one permission surface, and one persistence layer.", { lineColor: "DCE3EC", linePt: 1, bodySize: 10.4 });
  card(slide, 0.65, 5.35, 12.0, 1.1, C.white, "What makes the scope notable", "The project combines operational reliability concerns with user-facing delight. That combination is what makes the architecture and hosting decisions especially important.", { lineColor: "DCE3EC", linePt: 1, bodySize: 11 });
  footer(slide, 4);
  finalize(slide);

  slide = pptx.addSlide();
  background(slide);
  sectionTitle(
    slide,
    "System Architecture",
    "High-level runtime layout",
    "All capabilities are coordinated inside one Discord-connected Python process."
  );
  card(slide, 0.75, 1.6, 2.25, 0.95, C.navy, "Discord Clients", "Members, moderators, slash users, voice users.", { titleColor: C.white, bodyColor: C.white, bodySize: 10.3 });
  card(slide, 3.45, 1.6, 2.35, 0.95, C.blue, "Discord Runtime", "Gateway events, intents, commands, message stream.", { titleColor: C.white, bodyColor: C.white, bodySize: 10.3 });
  card(slide, 6.3, 1.6, 2.5, 0.95, C.cyan, "Bell Core", "Routing, scheduling, policy checks, state mutations.", { titleColor: C.white, bodyColor: C.white, bodySize: 10.3 });
  card(slide, 9.25, 1.6, 3.05, 0.95, C.ink, "External Integrations", "OpenRouter or Groq, Spotify, yt-dlp, ffmpeg, public APIs.", { titleColor: C.white, bodyColor: C.white, bodySize: 10.1 });
  addArrow(slide, 3.0, 2.07, 3.45, 2.07, C.blue);
  addArrow(slide, 5.8, 2.07, 6.3, 2.07, C.blue);
  addArrow(slide, 8.8, 2.07, 9.25, 2.07, C.blue);
  card(slide, 1.0, 3.0, 2.15, 1.15, C.sand, "Moderation Engine", "AutoMod, AI Guard, strike logic, review queue.", { bodySize: 10.2 });
  card(slide, 3.35, 3.0, 2.15, 1.15, "EEF8F6", "AI + NLP", "Assistant, summaries, capability routing, social AI.", { bodySize: 10.2, lineColor: "D6ECE8", linePt: 1 });
  card(slide, 5.7, 3.0, 2.15, 1.15, C.fog, "Engagement", "XP, streaks, quests, automation loops, onboarding.", { bodySize: 10.2, lineColor: "DCE3EC", linePt: 1 });
  card(slide, 8.05, 3.0, 2.15, 1.15, "E9F0F8", "Business", "Market simulation, taxes, property, businesses.", { bodySize: 10.2, lineColor: "D6E3F2", linePt: 1 });
  card(slide, 10.4, 3.0, 2.15, 1.15, C.white, "Music + Utility", "Voice playback and common server tools.", { bodySize: 10.2, lineColor: "DCE3EC", linePt: 1 });
  card(slide, 1.0, 5.0, 11.55, 1.1, C.white, "State and control plane", "JSON-backed files store warnings, mod config, AI moderation state, engagement state, business state, and capability metadata. Flush loops persist runtime state on intervals.", { lineColor: "DCE3EC", linePt: 1, bodySize: 11 });
  footer(slide, 5);
  finalize(slide);

  slide = pptx.addSlide();
  background(slide);
  sectionTitle(
    slide,
    "Request Lifecycle",
    "How a typical message is processed",
    "The runtime composes safety checks, routing, feature execution, and persistence."
  );
  const steps = [
    ["1. Event intake", "Discord delivers a message event into the bot runtime."],
    ["2. Safety gate", "AutoMod and AI Guard classify risk before normal feature handling."],
    ["3. Routing", "The bot decides between prefix commands, reply mode, natural language, or passive tracking."],
    ["4. Feature execution", "Business, AI, utility, music, engagement, or moderation handlers run."],
    ["5. State mutation", "Relevant state caches and dirty flags update in memory."],
    ["6. Response and loops", "The bot replies, logs actions, and scheduled flush loops persist state."],
  ];
  let sx = 0.72;
  for (let i = 0; i < steps.length; i++) {
    const fill = [C.navy, C.blue, C.cyan, C.sand, "EEF8F6", C.fog][i];
    const titleColor = i < 3 ? C.white : C.ink;
    const bodyColor = i < 3 ? C.white : C.ink;
    card(slide, sx, 2.2, 1.95, 2.45, fill, steps[i][0], steps[i][1], {
      titleColor,
      bodyColor,
      bodySize: 9.6,
      lineColor: i < 3 ? fill : "DCE3EC",
      linePt: i < 3 ? 0 : 1,
    });
    if (i < steps.length - 1) {
      addArrow(slide, sx + 1.95, 3.4, sx + 2.16, 3.4, C.blue);
    }
    sx += 2.08;
  }
  card(slide, 0.95, 5.3, 11.4, 1.05, C.white, "Engineering implication", "The same inbound event path is reused for moderation, natural language command resolution, AI assistance, and engagement tracking. That reuse is powerful, but it also increases coupling and operational complexity.", { lineColor: "DCE3EC", linePt: 1, bodySize: 10.8 });
  footer(slide, 6);
  finalize(slide);

  slide = pptx.addSlide();
  background(slide);
  sectionTitle(
    slide,
    "State and Persistence",
    "What data the bot keeps and why it matters",
    "Persistence is central because Bell is not stateless."
  );
  card(slide, 0.7, 1.65, 2.3, 1.2, C.fog, "warnings.json", "User warning history and moderation notes.", { lineColor: "DCE3EC", linePt: 1, bodySize: 10.2 });
  card(slide, 0.7, 3.0, 2.3, 1.2, C.fog, "mod_config.json", "Per-guild config such as automod, logs, loop settings, and policy toggles.", { lineColor: "DCE3EC", linePt: 1, bodySize: 10.2 });
  card(slide, 0.7, 4.35, 2.3, 1.2, C.fog, "ai_mod_state.json", "Cases, appeals, review actions, and risk tracking.", { lineColor: "DCE3EC", linePt: 1, bodySize: 10.2 });
  card(slide, 3.25, 1.65, 2.5, 1.2, "EEF8F6", "engagement_state.json", "XP, streaks, quests, events, and automation metadata.", { lineColor: "D6ECE8", linePt: 1, bodySize: 10.2 });
  card(slide, 3.25, 3.0, 2.5, 1.2, C.sand, "business_state.json", "Cash, portfolios, loans, markets, businesses, trades, and auctions.", { lineColor: "E4D7C1", linePt: 1, bodySize: 10.2 });
  card(slide, 3.25, 4.35, 2.5, 1.2, "E9F0F8", "capability catalog", "Natural-language discovery metadata for command recommendation.", { lineColor: "D6E3F2", linePt: 1, bodySize: 10.2 });
  card(slide, 6.05, 1.65, 2.9, 2.15, C.white, "Backend modes", "STATE_BACKEND=disk keeps JSON persistence on the host.\nSTATE_BACKEND=memory keeps features running but makes state ephemeral across restart.", { lineColor: "DCE3EC", linePt: 1, bodySize: 10.7 });
  card(slide, 6.05, 4.05, 2.9, 1.5, C.white, "Flush strategy", "Dirty state is written on loop intervals rather than on every event, which reduces churn but makes writable storage mandatory.", { lineColor: "DCE3EC", linePt: 1, bodySize: 10.4 });
  card(slide, 9.25, 1.65, 3.3, 3.9, C.navy, "Recent operational issue", "A full disk caused persistence writes to fail with errno 28. That exposed a hard runtime dependency: Bell can continue in memory, but persistent economy and engagement systems require free space or a remote database backend.", { titleColor: C.white, bodyColor: C.white, bodySize: 10.9 });
  footer(slide, 7);
  finalize(slide);

  slide = pptx.addSlide();
  background(slide);
  sectionTitle(
    slide,
    "AI Subsystems",
    "Bell uses AI for both utility and moderation",
    "The project mixes conversational AI with policy enforcement and social analysis."
  );
  card(slide, 0.65, 1.65, 2.9, 1.65, C.navy, "Assistant layer", "Chat, summaries, catch-up, command guidance, and server insights use provider-abstracted AI completion.", { titleColor: C.white, bodyColor: C.white, bodySize: 10.3 });
  card(slide, 3.8, 1.65, 2.9, 1.65, C.blue, "AI Guard", "Two-stage moderation: fast classification first, stricter judgment second, then case creation and optional enforcement.", { titleColor: C.white, bodyColor: C.white, bodySize: 10.3 });
  card(slide, 6.95, 1.65, 2.9, 1.65, C.cyan, "Psych + Argument", "Dedicated modes for supportive listening or adversarial debate, each with session memory and turn limits.", { titleColor: C.white, bodyColor: C.white, bodySize: 10.3 });
  card(slide, 10.1, 1.65, 2.55, 1.65, C.ink, "Social AI", "Roast, vibe, crush analysis, future predictions, and personality-style readouts.", { titleColor: C.white, bodyColor: C.white, bodySize: 10.1 });
  card(slide, 0.8, 3.8, 5.8, 2.0, C.white, "Guardrails already present", "Provider fallback models.\nRequest semaphore and retry logic.\nCircuit-break style protection.\nDedicated prompts for moderation versus fun use cases.\nStrict JSON parsing for classifier and judge outputs.", { lineColor: "DCE3EC", linePt: 1, bodySize: 10.8 });
  card(slide, 6.9, 3.8, 5.75, 2.0, C.sand, "Tradeoff to explain", "AI expands the product surface dramatically, but it also introduces API cost, latency, moderation risk, and external dependency failure modes. Bell therefore blends AI outputs with local heuristics and explicit policy controls.", { lineColor: "E4D7C1", linePt: 1, bodySize: 10.7 });
  footer(slide, 8);
  finalize(slide);

  slide = pptx.addSlide();
  background(slide);
  sectionTitle(
    slide,
    "Economy and Engagement",
    "Two state-heavy systems drive retention",
    "These subsystems are the most persistent and operationally demanding parts of the project."
  );
  card(slide, 0.65, 1.65, 5.85, 4.95, C.white, "Business engine", "Persistent user cash and portfolios.\nStocks, commodities, and crypto with risk controls.\nLoans, debt limits, taxes, credit, and market news.\nProperty ownership, upgrades, auctions, and player-to-player trades.\nPrivate business lifecycle with payroll, maintenance, and liquidation pressure.\nPeriodic market and world-event ticks.", { lineColor: "DCE3EC", linePt: 1, bodySize: 11 });
  card(slide, 6.82, 1.65, 5.85, 4.95, "EEF8F6", "Engagement engine", "XP and streak tracking.\nDaily quests and timed events.\nLeaderboard and rank snapshots.\nMini catch-up posts and onboarding concierge flows.\nGuild automation state and pacing controls.\nScheduled flush loops and heat/slowmode support.", { lineColor: "D6ECE8", linePt: 1, bodySize: 11 });
  footer(slide, 9);
  finalize(slide);

  slide = pptx.addSlide();
  background(slide);
  sectionTitle(
    slide,
    "Deployment and Operations",
    "Where Bell can run and what it needs",
    "This project behaves like a long-running service, not a stateless web app."
  );
  card(slide, 0.65, 1.7, 3.95, 1.55, C.navy, "Hard requirements", "Long-running process.\nDiscord gateway connection.\nMessage content and member intents.\nWritable persistent storage if state must survive restart.", { titleColor: C.white, bodyColor: C.white, bodySize: 10.5 });
  card(slide, 0.65, 3.45, 3.95, 1.55, C.blue, "Optional runtime dependencies", "AI provider keys.\nSpotify credentials.\nffmpeg for music.\nyt-dlp and voice dependencies.\nPublic API connectivity.", { titleColor: C.white, bodyColor: C.white, bodySize: 10.5 });
  card(slide, 0.65, 5.2, 3.95, 1.2, C.cyan, "Best-fit host types", "VPS, Render worker, Railway worker, Fly.io, or Oracle VM with persistent storage.", { titleColor: C.white, bodyColor: C.white, bodySize: 10.4 });
  card(slide, 4.95, 1.7, 3.55, 2.15, C.sand, "Why Vercel is a bad fit", "Discord bots need a stable websocket connection and always-on process. Serverless request-response platforms are not the right execution model.", { lineColor: "E4D7C1", linePt: 1, bodySize: 10.6 });
  card(slide, 8.8, 1.7, 3.85, 2.15, C.white, "Better next step", "Keep the bot on a worker or VM, then move persistence to Postgres or another managed store if local disk is unreliable.", { lineColor: "DCE3EC", linePt: 1, bodySize: 10.6 });
  card(slide, 4.95, 4.15, 7.7, 2.25, C.white, "Operations checklist", "Monitor disk usage.\nPrune large ledgers and caches.\nSeparate configuration from runtime state.\nCapture host-level failures such as no-space-left-on-device.\nTreat voice, AI, and API integrations as partial-failure boundaries.", { lineColor: "DCE3EC", linePt: 1, bodySize: 10.8 });
  footer(slide, 10);
  finalize(slide);

  slide = pptx.addSlide();
  background(slide);
  sectionTitle(
    slide,
    "Key Problems and Risks",
    "What this architecture makes hard",
    "The project is powerful, but the same breadth creates engineering pressure."
  );
  card(slide, 0.65, 1.75, 2.9, 2.0, C.white, "Monolithic runtime", "Most logic lives in one very large Python file, which increases coupling, makes testing harder, and raises the cost of safe refactoring.", { lineColor: "DCE3EC", linePt: 1, bodySize: 10.5 });
  card(slide, 3.8, 1.75, 2.9, 2.0, C.white, "Disk-sensitive state", "Economy and engagement features depend on persistence. If the host runs out of space, user trust can be damaged by lost progression.", { lineColor: "DCE3EC", linePt: 1, bodySize: 10.5 });
  card(slide, 6.95, 1.75, 2.9, 2.0, C.white, "External dependency volatility", "AI model availability, music extraction, API limits, and host networking can all degrade user experience independently of the core code.", { lineColor: "DCE3EC", linePt: 1, bodySize: 10.5 });
  card(slide, 10.1, 1.75, 2.55, 2.0, C.white, "Permission complexity", "Discord roles, moderation permissions, and voice networking rules introduce environment-specific edge cases.", { lineColor: "DCE3EC", linePt: 1, bodySize: 10.2 });
  card(slide, 0.9, 4.35, 11.75, 1.9, C.sand, "Important lesson", "Feature breadth does not only increase user value. It also multiplies operational states, storage pressure, and debugging surface area. Bell has crossed the point where platform engineering discipline matters as much as feature development.", { lineColor: "E4D7C1", linePt: 1, bodySize: 11 });
  footer(slide, 11);
  finalize(slide);

  slide = pptx.addSlide();
  background(slide);
  sectionTitle(
    slide,
    "Recommendations",
    "What would make the project production-strong",
    "The next phase should reduce coupling and improve operational safety."
  );
  card(slide, 0.65, 1.7, 3.0, 1.45, C.navy, "1. Move persistence to a database", "Postgres or a managed equivalent would remove host-disk fragility and support stronger recovery.", { titleColor: C.white, bodyColor: C.white, bodySize: 10.1 });
  card(slide, 3.95, 1.7, 3.0, 1.45, C.blue, "2. Split the monolith", "Modularize into cogs or services: moderation, AI, economy, engagement, music, utility.", { titleColor: C.white, bodyColor: C.white, bodySize: 10.1 });
  card(slide, 7.25, 1.7, 3.0, 1.45, C.cyan, "3. Add observability", "Structured logs, counters, disk alarms, flush health, and external API latency tracking.", { titleColor: C.white, bodyColor: C.white, bodySize: 10.1 });
  card(slide, 10.55, 1.7, 2.1, 1.45, C.ink, "4. Formalize hosting", "Use a worker or VM with explicit persistence guarantees.", { titleColor: C.white, bodyColor: C.white, bodySize: 9.8 });
  card(slide, 0.65, 3.6, 5.9, 2.5, C.white, "Product direction", "Keep Bell's strongest differentiator: one bot identity that spans governance, assistance, fun, and retention. The recommendation is not to shrink the product. It is to make the architecture worthy of the product scope.", { lineColor: "DCE3EC", linePt: 1, bodySize: 11.1 });
  card(slide, 6.85, 3.6, 5.8, 2.5, "EEF8F6", "Execution priority", "Start with persistence reliability and codebase modularization. Those two changes reduce the largest risks while preserving the current user-facing surface.", { lineColor: "D6ECE8", linePt: 1, bodySize: 11.1 });
  footer(slide, 12);
  finalize(slide);

  slide = pptx.addSlide();
  slide.background = { color: C.navy };
  slide.addText("Conclusion", {
    x: 0.8,
    y: 0.95,
    w: 2.6,
    h: 0.28,
    fontFace: FONT_BODY,
    fontSize: 9,
    bold: true,
    color: C.mint,
    charSpace: 1.2,
    margin: 0,
  });
  slide.addText("Bell is already more than a bot.", autoFontSize("Bell is already more than a bot.", FONT_HEAD, {
    x: 0.8,
    y: 1.35,
    w: 6.8,
    h: 0.8,
    fontSize: 28,
    minFontSize: 24,
    maxFontSize: 34,
    bold: true,
    color: C.white,
    margin: 0,
  }));
  slide.addText(
    "It is a compact community platform with moderation, AI, gameplay, and engagement systems in one runtime.\n\nThe strongest story is not only what Bell can do today. It is that the project clearly demonstrates how product ambition eventually forces architecture, persistence, and deployment maturity.",
    {
      x: 0.8,
      y: 2.35,
      w: 6.7,
      h: 2.3,
      fontFace: FONT_BODY,
      fontSize: 13,
      color: C.white,
      margin: 0,
      valign: "top",
    }
  );
  tag(slide, 0.8, 5.2, "Moderation", C.cyan, C.white, 1.3);
  tag(slide, 2.25, 5.2, "AI", C.mint, C.ink, 0.9);
  tag(slide, 3.3, 5.2, "Economy", "D1972B", C.white, 1.2);
  tag(slide, 4.65, 5.2, "Engagement", C.blue, C.white, 1.55);
  tag(slide, 6.35, 5.2, "Music", C.steel, C.white, 1.0);
  card(slide, 8.95, 1.25, 3.45, 4.7, C.white, "Final message", "Bell is a strong showcase of product breadth, event-driven engineering, and iterative hardening. The next milestone is to convert that breadth into a more production-safe platform architecture.", { lineColor: "DCE3EC", linePt: 1, bodySize: 11.3 });
  footer(slide, 13);
  finalize(slide);
}

async function main() {
  build();
  await pptx.writeFile({ fileName: OUT_FILE });
  console.log(`Wrote ${OUT_FILE}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
