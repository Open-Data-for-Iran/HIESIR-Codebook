/* Code to copy: the codes to add up in each year, as Python. No DOM. */

/* cmp: a comparison from compare() or gcompare(); the years it cannot
   express (not asked, or not recoverable) are left out */
export function codesSnippet(years, cmp, header) {
  const py = [header, "# codes to add up in each year (the raw data's Commodity_Code)", "codes = {"];
  for (const y of years) {
    const e = cmp.get(y);
    if (e && e.st !== null && e.st !== 3) py.push(`    ${y}: [${e.set.map(x => Number(x.code)).join(", ")}],`);
  }
  py.push("}");
  return py.join("\n");
}
