import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const outputs = JSON.parse(fs.readFileSync(path.join(root, "scenarios/live_capture_outputs.json"), "utf8"));
const scenarioLabels = {
  "overpowered-data-tool": "Overpowered Data Tool",
  "cross-customer-access": "Cross-Account Access",
  "signed-handoff": "Unsafe Agent Handoff",
  "business-rule": "Refund Limit Bypass",
  "indirect-injection": "Poisoned Invoice Instructions",
  "rag-tenant-isolation": "Multi-tenant RAG Leakage",
  "secret-leakage": "Secret Leakage Through Debugging",
  "approval-service-outage": "Approval Service Outage",
  "multi-agent-confused-deputy": "Confused Deputy Agent Chain",
};

const xml = (value) => String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const wrap = (line, width = 112) => {
  if (!line) return [""];
  const parts = [];
  let remaining = line;
  while (remaining.length > width) {
    let cut = remaining.lastIndexOf(" ", width);
    if (cut < Math.floor(width * 0.55)) cut = width;
    parts.push(remaining.slice(0, cut));
    remaining = remaining.slice(cut).trimStart();
  }
  parts.push(remaining);
  return parts;
};
const linesFor = (response) => response.split("\n").flatMap((line) => wrap(line));

for (const [scenarioId, modes] of Object.entries(outputs)) {
  const title = scenarioLabels[scenarioId] || scenarioId;
  const folder = scenarioId.replaceAll("-", "_");
  const attackPresetLabel = "Vulnerable-mode attack";
  for (const [mode, capture] of Object.entries(modes)) {
    const lines = linesFor(capture.response);
    const fontSize = lines.length > 34 ? 14 : lines.length > 25 ? 16 : 18;
    const lineHeight = fontSize + 11;
    const responseTop = 342;
    const responseBottom = responseTop + Math.max(120, lines.length * lineHeight + 28);
    const proofTop = responseBottom + 36;
    const height = proofTop + 128 + 58;
    const responseText = lines.map((line, index) => `<text x="78" y="${responseTop + 24 + index * lineHeight}" fill="#f3f1ea" font-family="monospace" font-size="${fontSize}">${xml(line)}</text>`).join("\n");
    const proof = mode === "vulnerable"
      ? `The live Vulnerable posture returned the raw result produced by the ${attackPresetLabel} preset.`
      : "The live Hardened posture returned only the application-authorized result for the same attack preset.";
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="${height}" viewBox="0 0 1440 ${height}" role="img" aria-labelledby="title desc">
  <title id="title">Live ${mode} response from the ${xml(title)} lab</title>
  <desc id="desc">Captured from the interactive lab using the ${xml(attackPresetLabel)} preset.</desc>
  <rect width="1440" height="${height}" fill="#f3f1ea"/>
  <rect x="44" y="38" width="1352" height="${height - 76}" rx="4" fill="#252620"/>
  <text x="78" y="86" fill="#f3f1ea" font-family="monospace" font-size="18" letter-spacing="3">WHO LET THE AGENTS ACT / LIVE LAB CAPTURE</text>
  <rect x="1150" y="58" width="210" height="42" rx="2" fill="${capture.verdict === "EXPOSED" ? "#d84d3d" : "#5f9e73"}"/>
  <text x="1255" y="85" text-anchor="middle" fill="#fff" font-family="monospace" font-size="16" font-weight="700">${xml(capture.verdict)}</text>
  <text x="78" y="148" fill="#bbbdb3" font-family="monospace" font-size="15" letter-spacing="2">SCENARIO</text>
  <text x="78" y="184" fill="#f3f1ea" font-family="sans-serif" font-size="27" font-weight="700">${xml(title)} · ${mode === "vulnerable" ? "Vulnerable" : "Hardened"}</text>
  <text x="78" y="224" fill="#bbbdb3" font-family="monospace" font-size="15" letter-spacing="2">RUN INPUT</text>
  <text x="78" y="258" fill="#f3f1ea" font-family="monospace" font-size="20">${xml(attackPresetLabel)} preset</text>
  <line x1="78" y1="286" x2="1362" y2="286" stroke="#55574e"/>
  <text x="78" y="326" fill="#d84d3d" font-family="monospace" font-size="16" letter-spacing="2">OBSERVED RESPONSE</text>
${responseText}
  <rect x="78" y="${proofTop}" width="1284" height="128" rx="2" fill="#33342d"/>
  <text x="108" y="${proofTop + 40}" fill="#d84d3d" font-family="monospace" font-size="16" letter-spacing="2">WHAT THIS PROVES</text>
  <text x="108" y="${proofTop + 76}" fill="#f3f1ea" font-family="sans-serif" font-size="21">${xml(proof)}</text>
  <text x="108" y="${proofTop + 108}" fill="#bbbdb3" font-family="sans-serif" font-size="18">Source: interactive lab output captured for this scenario.</text>
</svg>
`;
    fs.writeFileSync(path.join(root, "scenarios", folder, "screenshots", `live-${mode}-response.svg`), svg);
  }
}
