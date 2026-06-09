// Phase 1 Index JSON Schema
import { z } from "zod";

export const confidenceEnum = z.enum(["确定","存疑"]);
export const priorityEnum = z.enum(["P0","P1","P2","P3"]);
export const categoryEnum = z.enum(["君纪","士臣","事略","典制","民录","著作"]);

export const indexItemSchema = z.object({
  entity: z.string().min(1), type: categoryEnum,
  paragraphs: z.array(z.number().int().positive()).min(1),
  bio: z.string().optional(), context: z.string().optional(), note: z.string().optional(),
  key_events: z.array(z.string()).optional(),
  related_systems: z.array(z.string()).optional(),
  related_characters: z.array(z.string()).optional(),
  priority: priorityEnum, priority_reason: z.string().optional(),
  weight: z.string().optional(), confidence: confidenceEnum,
});

export const phase1OutputSchema = z.object({
  book: z.string().min(1), volume: z.string().min(1), chapter: z.string().min(1),
  scan_log: z.array(z.object({ paragraph: z.number(), results: z.string() })),
  characters: z.array(indexItemSchema), events: z.array(indexItemSchema),
  systems: z.array(indexItemSchema), folklore: z.array(indexItemSchema),
  works: z.array(indexItemSchema),
  review_summary: z.object({ grand_total: z.number(), confirmed: z.number(), uncertain: z.number(), notes: z.string() }).passthrough(),
}).passthrough();

export class ValidationReport { errors=[]; warnings=[]; stats={}; get valid() { return this.errors.length===0; } }
