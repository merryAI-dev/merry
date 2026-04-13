import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { getVisibleProducts } from "@/lib/products";
import { getWorkspaceFromCookies } from "@/lib/workspaceServer";

export default async function ProductsPage() {
  const workspace = await getWorkspaceFromCookies();
  const products = getVisibleProducts(workspace);

  return (
    <div
      className="min-h-full px-6 py-12 md:px-10"
      style={{
        background:
          "radial-gradient(circle at top left, rgba(0, 200, 5, 0.09), transparent 34%), linear-gradient(180deg, #F7F8F9 0%, #FFFFFF 45%, #F7F8F9 100%)",
      }}
    >
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-10">
        <div className="max-w-2xl">
          <div
            className="text-sm font-semibold uppercase tracking-[0.22em]"
            style={{ color: "#6F7780" }}
          >
            Product Gateway
          </div>
          <h1
            className="mt-3 text-4xl font-black tracking-tight text-[#1A1D21] md:text-5xl"
            style={{ fontFamily: "var(--font-merry-display, var(--font-korean))" }}
          >
            어떤 작업을 시작할까요
          </h1>
          <p
            className="mt-4 max-w-xl text-base leading-7 md:text-lg"
            style={{ color: "#6F7780", fontFamily: "var(--font-korean, system-ui)" }}
          >
            로그인과 팀은 공유하지만, 실제 작업 공간은 제품별로 분리됩니다.
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          {products.map((product) => (
            <Link
              key={product.slug}
              href={product.href}
              className="group rounded-[28px] border border-[#E3E5E8] bg-white p-7 shadow-[0_8px_28px_rgba(26,29,33,0.06)] transition-transform duration-150 hover:-translate-y-1 hover:shadow-[0_18px_40px_rgba(26,29,33,0.1)]"
            >
              <div
                className="inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold"
                style={{
                  background: product.slug === "review" ? "rgba(0,200,5,0.10)" : "rgba(59,130,246,0.10)",
                  color: product.slug === "review" ? "#00A803" : "#2563EB",
                }}
              >
                {product.label}
              </div>

              <h2
                className="mt-4 text-2xl font-black tracking-tight text-[#1A1D21]"
                style={{ fontFamily: "var(--font-merry-display, var(--font-korean))" }}
              >
                {product.description}
              </h2>

              <div className="mt-8 flex items-center justify-between">
                <span className="text-sm font-semibold" style={{ color: "#6F7780" }}>
                  작업 공간 열기
                </span>
                <span
                  className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-[#E3E5E8] transition-transform duration-150 group-hover:translate-x-0.5"
                  style={{ color: "#1A1D21" }}
                >
                  <ArrowRight className="h-4 w-4" />
                </span>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
