// Duplicate name detector for Phase 1 index output
import { readFileSync } from "fs";
import { resolve } from "path";

const inputFile = resolve(process.argv[3] || "./sample.json");
console.log("Checking for duplicates in: ", inputFile);

try {
  const data = JSON.parse(readFileSync(inputFile, "utf8"));
  const allChars = data.characters || [];
  const nameMap = new Map();
  allChars.forEach(c => {
    const name = c.entity.toLowerCase();
    if (!nameMap.has(name)) nameMap.set(name, []);
    nameMap.get(name).push({ entity: c.entity, type: c.type, paragraphs: c.paragraphs });
  });
  const dupes = [...nameMap.entries()].filter(([k,v]) => v.length > 1);
  if (dupes.length === 0) {
    console.log("PASS - No duplicate names found");
    process.exit(0);
  } else {
    console.log("Potential duplicates:");
    dupes.forEach(([name, entries]) => {
      console.log("  "+entries[0].entity+": "+entries.length+" entries");
      entries.forEach(e => console.log("    - type="+e.type+" paragraphs="+JSON.stringify(e.paragraphs)));
    });
    process.exit(1);
  }
} catch (e) {
  console.error("FAIL - "+e.message);
  process.exit(1);
}