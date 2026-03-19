/**
 * Self-Critique and Refinement — GOLF Section 4.3 Joint Optimization
 *
 * Generation and refinement form a virtuous cycle:
 * - Better refinement → better off-policy scaffolds
 * - Better scaffolds → more efficient generation
 * - Better generation → richer material for refinement
 *
 * This module provides:
 * 1. Critique prompt construction (external critique)
 * 2. Refinement prompt construction (conditioned on critique)
 */

import { buildSelfCritiquePrompt } from "@/lib/merryPersona";

export type CritiqueItem = {
  category: "사실" | "논리" | "누락" | "톤";
  description: string;
};

/**
 * Build the full critique request for the LLM.
 * The LLM will review the draft and output structured critique items.
 */
export function buildCritiqueMessages(draft: string, context?: string): Array<{ role: "user" | "assistant"; content: string }> {
  const systemCtx = context ? `\n\n[컨텍스트]\n${context}` : "";

  return [
    {
      role: "user",
      content: `${buildSelfCritiquePrompt()}${systemCtx}\n\n---\n\n## 검토 대상 초안:\n\n${draft}`,
    },
  ];
}

/**
 * Build the refinement request conditioned on critique.
 * GOLF Appendix B pattern: present original + critique → synthesize improved version.
 */
export function buildRefinementMessages(
  originalDraft: string,
  critique: string,
): Array<{ role: "user" | "assistant"; content: string }> {
  return [
    {
      role: "user",
      content: [
        "아래 초안과 감수 의견을 바탕으로 개선된 버전을 작성해주세요.",
        "",
        "## 규칙",
        "- 감수 의견에서 지적된 [사실] 오류는 반드시 수정",
        "- [논리] 비약은 근거를 추가하거나 주장을 완화",
        "- [누락] 항목은 가능한 추가, 정보가 없으면 [확인 필요]로 표시",
        "- [톤] 문제는 인수인의견 스타일로 조정",
        "- 감수 의견이 없는 부분은 원본 유지",
        "- 개선된 본문만 출력 (메타 코멘트 금지)",
        "",
        "## 원본 초안",
        originalDraft,
        "",
        "## 감수 의견",
        critique,
      ].join("\n"),
    },
  ];
}

/**
 * Parse structured critique items from LLM response.
 */
export function parseCritiqueItems(critiqueText: string): CritiqueItem[] {
  const items: CritiqueItem[] = [];
  const regex = /\[(사실|논리|누락|톤)\]\s*(.+)/g;
  let match;
  while ((match = regex.exec(critiqueText)) !== null) {
    items.push({
      category: match[1] as CritiqueItem["category"],
      description: match[2].trim(),
    });
  }
  return items;
}
