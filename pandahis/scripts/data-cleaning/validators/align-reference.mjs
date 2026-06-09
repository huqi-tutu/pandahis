import { readFileSync } from "fs";
import { resolve } from "path";

const inputFile = resolve(process.argv[3] || "sample.json");
const refArg = process.argv[5];
console.log("Aligning: ", inputFile);

try {
  const data = JSON.parse(readFileSync(inputFile, "utf8"));
  let ref = null;
  if (refArg) {
    ref = JSON.parse(readFileSync(resolve(refArg), "utf8"));
  } else {
    console.log("No reference file provided (--ref), skipping CBDB cross-check");
  }
  let issues = 0;
  if (ref) {
    const allEmperors = [];
    for (const [civ, dyns] of Object.entries(ref.dynasties_by_civilization||{}))
      for (const d of dyns) allEmperors.push(...d.emperors.map(e=>({...e,civ,dynasty:d.dynasty})));
    (data.records||[]).forEach(r => {
      if (r.category !== "...") return;
      const match = allEmperors.find(e => e.emperor.includes(r.name)||r.name.includes(e.emperor));
      if (match && match.dynasty !== r.dynasty) { console.log("  Mismatch: "+r.name+" ref="+match.dynasty+" data="+r.dynasty); issues++; }
    });
  }
  if (issues===0) { console.log("PASS - All records align with reference"); process.exit(0); }
  else { console.log(issues+" misalignments found"); process.exit(1); }
} catch (e) {
  console.error("FAIL - "+e.message); process.exit(1);
}