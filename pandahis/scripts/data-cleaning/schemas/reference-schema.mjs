// CBDB Reference Data Schema
import { z } from "zod";

export const emperorSchema = z.object({
  emperor: z.string().min(1), regime: z.string().min(1),
  start_year: z.number().int(), end_year: z.number().int(),
});

export const dynastySchema = z.object({
  dynasty: z.string().min(1), start_year: z.number().int(), end_year: z.number().int(),
  emperors: z.array(emperorSchema), emperor_count: z.number().int().nonnegative(),
});

export const referenceSchema = z.object({
  source: z.string(), last_synced: z.string(),
  civilizations: z.array(z.string()),
  dynasties_by_civilization: z.record(z.array(dynastySchema)),
});
