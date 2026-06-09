// Phase 3 Compose Output Schema - Zod Validation
import { z } from "zod";

export const composeRecordSchema = z.object({
  史略ID: z.string().min(1), 史略名称: z.string().min(1),
  史略简介_20字以内: z.string().max(20),
  史略分类: z.enum(["君纪","士臣","事略","典制","民录","著作"]),
  一级文明归属: z.string().min(1), 二级王朝归属: z.string().min(1),
  三级帝王归属: z.string().min(1), 史略开始年: z.number(), 史略结束年: z.number(),
  时间精度: z.enum(["A","B","C","D"]),
  时间备注: z.string(), 优先级: z.enum(["P0","P1","P2"]),
  优先级判定理由: z.string(), 主要史料出处: z.string(),
  史料原文: z.string(), 详情: z.string().min(1),
  审核摘要: z.enum(["确定","存疑"]),
  更新时间: z.string(),
});

export const composeOutputSchema = z.object({
  records: z.array(composeRecordSchema).min(1),
});

export class ComposeValidationReport { errors=[]; warnings=[]; stats={}; get valid() { return this.errors.length===0; } }
