import { phase1OutputSchema, ValidationReport } from "../schemas/index-schema.mjs";
import { readFileSync } from "fs";
import { resolve } from "path";

const inputFile = resolve(process.argv[3] || "./sample.json");
console.log("Validating: ", inputFile);

try {
  const raw = readFileSync(inputFile, "utf8");
  const data = JSON.parse(raw);
  const result = phase1OutputSchema.safeParse(data);
  if (result.success) {
    console.log("PASS - Schema valid");
    console.log("Book: ", data.book);
    console.log("Volume: ", data.volume);
    console.log("Characters: ", data.characters?.length);
    console.log("Events: ", data.events?.length);
    console.log("Total: ", data.review_summary?.grand_total);
    process.exit(0);
  } else {
    console.error("FAIL - Schema errors:");
    result.error.issues.forEach(i => {
      console.error("  ["+i.path.join('.')+"] "+i.message);
    });
    process.exit(1);
  }
} catch (e) {
  console.error("FAIL - "+e.message);
  process.exit(1);
}
