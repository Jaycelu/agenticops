/**
 * Case / Event status Chinese labels.
 * Shared by Cases.vue, Events.vue, Dashboard/Home.vue.
 */
export const CASE_STATUS_LABELS: Record<string, string> = {
  new: "新建",
  normalized: "已规整",
  open: "打开",
  triaged: "已分诊",
  evidence_collecting: "证据收集中",
  diagnosing: "诊断中",
  hypothesis_review: "假设审查",
  planning: "计划中",
  safety_review: "安全审查",
  awaiting_approval: "等待审批",
  investigating: "调查中",
  planned: "已计划",
  executing: "执行中",
  verifying: "验证中",
  observing: "观察中",
  resolved: "已解决",
  rolled_back: "已回滚",
  escalated: "已升级",
  failed: "失败",
  closed: "已关闭",
  pending: "等待中",
  approved: "已批准",
  draft: "草案",
}

export const CASE_PHASE_LABELS: Record<string, string> = {
  intake: "接入",
  analysis: "分析",
  remediation_draft: "修复草案",
}

/**
 * Get Chinese label for a case/event status.
 */
export function formatStatus(status: string | null | undefined): string {
  if (!status) return ""
  return CASE_STATUS_LABELS[status.toLowerCase()] ?? status
}
