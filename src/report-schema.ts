import { z } from 'zod';
const text = z.string().min(1).max(6000);
const refs = z.array(z.string()).max(20);
const statement = z.object({ kind: z.enum(['事实','推断','预测']), text, sourceIds: refs });
const idea = z.object({ id: text, name: text, code: z.string(), sector: text, status: z.enum(['等待验证','深入研究','估值观察','条件满足','逻辑失效']), thesis: text, valuation: text, catalyst: text, action: text, invalidation: text, horizon: text, evidence: z.array(statement).min(1).max(15), sourceIds: refs });
export const reportSchema = z.object({
  freshness: z.object({checkedAt:text,researchUpdatedAt:text,mode:text,reason:text}).optional(),
  evidenceUpdates: z.array(z.object({title:text,publisher:text,url:z.string().url(),publishedAt:text,summary:text})).optional(),
  schemaVersion: z.literal(1), date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/), edition: z.enum(['AM','PM']),
  title: text, subtitle: text, publishedAt: z.string().datetime({ offset: true }), cutoff: text,
  completeness: z.enum(['已核验','部分数据待核实']), coverageNote: text,
  conclusions: z.array(z.object({ label: text, title: text, body: text, kind: z.enum(['事实','推断','预测']), sourceIds: refs })).min(3).max(5),
  markets: z.array(z.object({ name: text, code: text, value: z.number().nullable(), change: z.number().nullable(), changeUnit:z.enum(['%','bp']).optional(), unit: text, asOf: z.string(), timezone: text, status: text, sourceIds: refs })).min(6).max(16),
  macro: z.array(z.object({ title: text, fact: text, transmission: text, watch: text, sourceIds: refs })).min(1).max(8),
  flow: z.object({ observation: text, interpretation: text, sourceIds: refs }),
  ideas: z.array(idea).min(3).max(15), companies: z.array(idea.extend({ metrics: z.array(z.object({ label: text, value: text, note: text })).min(3).max(12), period: text })).min(1).max(8),
  assets: z.array(z.object({ name: text, role: text, valuation: text, fee: text, action: text, risk: text, sourceIds: refs })).min(3).max(12),
  strategy: z.object({ stance: text, actions: z.array(text).min(2).max(8), scenarios: z.array(z.object({ name: text, trigger: text, response: text })).min(2).max(6), catalysts: z.array(z.object({ date: text, event: text, watch: text, sourceIds: refs })).max(12) }),
  tracking: z.array(z.object({ id: text, name: text, firstSeen: z.string(), status: text, originalThesis: text, update: text, invalidation: text, sourceIds: refs })).min(1).max(50),
  sources: z.array(z.object({ id: text, title: text, publisher: text, url: z.string().url().refine(u=>u.startsWith('https://'),'HTTPS required'), publishedDate: text, dataPeriod: text, accessedAt: text })).min(3).max(80)
}).strict().superRefine((r,ctx)=>{
  const ids=new Set(r.sources.map(s=>s.id));
  if(ids.size!==r.sources.length) ctx.addIssue({code:'custom',message:'Duplicate source IDs'});
  const check=(v:unknown):void=>{ if(!v||typeof v!=='object')return; if(Array.isArray(v)){v.forEach(check);return;}
    const o=v as Record<string,unknown>;
    if(Array.isArray(o.sourceIds)){ for(const id of o.sourceIds)if(!ids.has(String(id)))ctx.addIssue({code:'custom',message:`Unknown source ${id}`}); if(o.kind==='事实'&&!o.sourceIds.length)ctx.addIssue({code:'custom',message:'Facts require sources'}); }
    Object.values(o).forEach(check);
  }; check(r);
  r.markets.forEach(m=>{ if(m.value!==null&&(!m.asOf||!m.sourceIds.length))ctx.addIssue({code:'custom',message:'Quotes require timestamp and sources'}); if(m.value===null&&m.change!==null)ctx.addIssue({code:'custom',message:'Missing quote must not have a change'}); });
});
export type Report = z.infer<typeof reportSchema>;
export type Idea = Report['ideas'][number];

