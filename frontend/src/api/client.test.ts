import { buildQuery } from "@/api/client";

describe("buildQuery", () => {
  it("omite valores vazios e repete arrays", () => {
    expect(buildQuery({ a: 1, b: "", c: undefined, d: [1, 2] })).toBe("?a=1&d=1&d=2");
  });
  it("devolve string vazia sem parâmetros", () => {
    expect(buildQuery({})).toBe("");
  });
});
