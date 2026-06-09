import { composeOutputSchema } from "../schemas/compose-schema.mjs";
import { readFileSync } from "fs";
import { resolve } from "path";

const inputFile = resolve(process.argv[3] || "./sample.json");
console.log("Validating: ", inputFile);

try {
  const raw = readFileSync(inputFile, "utf8");
  const data = JSON.parse(raw);
  const result = composeOutputSchema.safeParse(data);
  if (result.success) {
    console.log("PASS - Schema valid");
    console.log("Records: ", data.records.length);
    const cats = {};
    data.records.forEach(r => { cats[r.category] = (cats[r.category]||0)+1; });
    console.log("Categories: ", JSON.stringify(cats));
    const emptyFields = data.records.filter(r => !r.detail || !r.name || !r.ID);
    if (emptyFields.length) console.log("WARNING: "+emptyFields.length+" records have empty required fields");
    process.exit(0);
  } else {
    console.error("FAIL:");
    result.error.issues.forEach(i => console.error("  "+i.path.join('.')+": "+i.message));
    process.exit(1);
  }
} catch (e) {
  console.error("FAIL - "+e.message);
  process.exit(1);
}
