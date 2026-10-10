import { readFile, writeFile } from "node:fs/promises";
import openapiTS, { astToString } from "openapi-typescript";
import ts from "typescript";

const schema = new URL("../../backend/openapi.json", import.meta.url);
const destination = new URL("../src/shared/api/schema.ts", import.meta.url);
const ast = await openapiTS(schema, {
  transform(value) {
    if (value.format === "binary" || value.contentMediaType === "application/octet-stream") {
      return ts.factory.createTypeReferenceNode("Blob");
    }
  },
});
const generated = "// Generated from backend/openapi.json. Run npm run api:generate.\n" + astToString(ast);
if (process.argv.includes("--check")) {
  const existing = await readFile(destination, "utf8").catch(() => "");
  if (existing.replace(/\r\n/g, "\n") !== generated) {
    throw new Error("API types are stale. Regenerate OpenAPI, then run npm run api:generate.");
  }
  console.log("TypeScript API types match OpenAPI");
} else {
  await writeFile(destination, generated);
  console.log("Generated src/shared/api/schema.ts");
}
