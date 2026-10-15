import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { Bar, Line } from 'react-chartjs-2'
import { CategoryScale, Chart as ChartJS, Filler, Legend, LinearScale, LineElement, PointElement, BarElement, Tooltip } from 'chart.js'
import { api, downloadReport, post, put } from './services/api'
import type { Action, Forecast, Metric, Recommendation, Resource, Summary } from './types'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Tooltip, Legend, Filler)
const money = (cents: number) => '$' + (cents / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const dateLabel = (value: string) => new Date(value).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit' })
const badgeClass = (value: string) => ['running','approved','executed','available'].includes(value) ? 'badge badge-green' : ['pending','medium'].includes(value) ? 'badge badge-amber' : ['high','failed','rejected','stopped'].includes(value) ? 'badge badge-red' : 'badge badge-gray'

export function ErrorNotice({ error }: { error: string }) { return error ? <div className="error">{error}</div> : null }
function useLoad<T>(path: string) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const reload = useCallback(async () => { setLoading(true); try { setData(await api<T>(path)); setError('') } catch (e) { setError(e instanceof Error ? e.message : 'Could not load data') } finally { setLoading(false) } }, [path])
  useEffect(() => { void reload() }, [reload])
  return { data, error, loading, reload, setError }
}

function Heading({ title, description, action }: { title:string; description:string; action?:ReactNode }) {
  return <div className="page-heading"><div><h1>{title}</h1><p>{description}</p></div>{action}</div>
}
function SimulatedBanner() { return <div className="sim-banner"><span>◈</span><span><strong>SIMULATED ENVIRONMENT</strong> · Generated telemetry and savings estimates. No live cloud data or actions.</span></div> }
function StatCard({ label, value, detail }: { label:string; value:string; detail:string }) {
  return <div className="card"><div className="card-title">{label}</div><div className="stat-value">{value}</div><div className="stat-caption">{detail}</div></div>
}
function Loading() { return <div className="empty">Loading local demo data…</div> }
function Empty({ children }: {children:ReactNode}) { return <div className="empty">{children}</div> }

export function DashboardPage() {
  const summary = useLoad<Summary>('/dashboard/summary')
  const resources = useLoad<Resource[]>('/resources')
  const [metrics, setMetrics] = useState<Metric[]>([])
  const [metricError, setMetricError] = useState('')
  useEffect(() => {
    if (!resources.data?.length) return
    api<Metric[]>('/resources/' + encodeURIComponent(resources.data[0].id) + '/metrics?limit=168')
      .then(setMetrics).catch(e => setMetricError(e instanceof Error ? e.message : 'Metrics unavailable'))
  }, [resources.data])
  if (summary.loading) return <Loading />
  const s = summary.data
  const byDay = new Map<string, number[]>()
  metrics.forEach(m => { const key = new Date(m.observed_at).toLocaleDateString([], { month:'short', day:'numeric' }); byDay.set(key, [...(byDay.get(key) ?? []), m.cpu_percent]) })
  const labels = [...byDay.keys()]
  const cpuData = [...byDay.values()].map(values => values.reduce((a,b) => a+b,0) / values.length)
  return <><Heading title="Cost overview" description="A live view of your local simulated cloud environment." /><SimulatedBanner /><ErrorNotice error={summary.error || metricError} />
    <div className="grid grid-4">
      <StatCard label="Estimated monthly cost" value={s ? money(s.estimated_monthly_cost_cents) : '—'} detail="Run rate at current simulated state" />
      <StatCard label="Simulated resources" value={String(s?.resource_count ?? 0)} detail={(s?.running_count ?? 0) + ' currently running'} />
      <StatCard label="Average CPU · 24h" value={s?.average_cpu_percent_24h == null ? '—' : s.average_cpu_percent_24h + '%'} detail="Across recorded simulated metrics" />
      <StatCard label="Hourly run rate" value={s ? money(s.hourly_cost_cents) : '—'} detail="Estimated cost per simulated hour" />
    </div>
    <div className="grid grid-2" style={{marginTop:16}}>
      <div className="card"><div className="panel-head"><h2 className="section-title">Utilization trend</h2><span className="badge badge-blue">SIMULATED</span></div>
        {cpuData.length ? <Line data={{ labels, datasets:[{label:'CPU utilization',data:cpuData,borderColor:'#3764ed',backgroundColor:'#3764ed18',fill:true,tension:.35,pointRadius:0,borderWidth:2}] }} options={{responsive:true,plugins:{legend:{display:false}},scales:{y:{min:0,max:100,ticks:{callback:v=>v+'%'}},x:{grid:{display:false}}}}} /> : <Empty>{metricError || 'Historical utilization appears after the API is seeded.'}</Empty>}
        {resources.data?.[0] && <div className="stat-caption">Example resource: {resources.data[0].name}</div>}
      </div>
      <div className="card"><h2 className="section-title">Cost by resource category</h2>
        {s?.categories.length ? <Bar data={{labels:s.categories.map(x=>x.category),datasets:[{label:'Hourly estimated cost',data:s.categories.map(x=>x.hourly_cost_cents/100),backgroundColor:'#7591f3',borderRadius:5}]}} options={{responsive:true,plugins:{legend:{display:false}},scales:{y:{beginAtZero:true,ticks:{callback:v=>'$'+v}},x:{grid:{display:false}}}}} /> : <Empty>No category data available.</Empty>}
      </div>
    </div>
  </>
}

export function ResourcesPage() {
  const {data, error, loading} = useLoad<Resource[]>('/resources')
  const [selected,setSelected] = useState('')
  const [metrics,setMetrics] = useState<Metric[]>([])
  useEffect(() => { if (selected) void api<Metric[]>('/resources/'+encodeURIComponent(selected)+'/metrics?limit=168').then(setMetrics).catch(()=>setMetrics([])) },[selected])
  const resources=data??[]
  const chosen=resources.find(r=>r.id===selected)
  return <><Heading title="Resources" description="Inventory and historical utilization for simulated resources."/><SimulatedBanner/><ErrorNotice error={error}/>
    {loading ? <Loading/> : <><div className="table-wrap"><table><thead><tr><th>Resource</th><th>Category</th><th>Region</th><th>Size</th><th>Status</th><th>Monthly estimate</th><th></th></tr></thead><tbody>
      {resources.map(r=><tr key={r.id}><td><strong>{r.name}</strong><div className="muted">{r.id}</div></td><td>{r.category}</td><td>{r.region}</td><td>{r.size}</td><td><span className={badgeClass(r.status)}>{r.status}</span></td><td>{money(r.estimated_monthly_cost_cents)}</td><td><button className="button" onClick={()=>setSelected(r.id)}>View metrics</button></td></tr>)}
    </tbody></table></div>
    {chosen&&<div className="card" style={{marginTop:16}}><div className="panel-head"><h2 className="section-title">{chosen.name} · historical utilization</h2><span className="badge badge-blue">SIMULATED</span></div>
      {metrics.length?<Line data={{labels:metrics.map(x=>dateLabel(x.observed_at)),datasets:[{label:'CPU %',data:metrics.map(x=>x.cpu_percent),borderColor:'#3764ed',pointRadius:0,tension:.25},{label:'Memory %',data:metrics.map(x=>x.memory_percent),borderColor:'#16a673',pointRadius:0,tension:.25}]}} options={{responsive:true,plugins:{legend:{position:'bottom'}},scales:{y:{min:0,max:100,ticks:{callback:v=>v+'%'}},x:{ticks:{maxTicksLimit:10}}}}}/>:<Empty>Select data is not available.</Empty>}
      <div className="stat-caption">Storage utilization and network throughput are available in the underlying metric records.</div>
    </div>}</>}
  </>
}

export function ForecastsPage() {
  const {data,reload,error,loading,setError}=useLoad<Forecast[]>('/forecasts')
  const [busy,setBusy]=useState(false)
  const [message,setMessage]=useState('')
  const generate=async()=>{setBusy(true);setError('');setMessage('');try{const result=await post<{results:{status:string;model:string|null;message:string|null}[]}>('/forecasts/generate',{horizon_hours:168});const statuses=[...new Set(result.results.map(x=>x.status))];setMessage(result.results.length+' resources processed · '+statuses.join(', '));await reload()}catch(e){setError(e instanceof Error?e.message:'Forecast generation failed')}finally{setBusy(false)}}
  const forecasts=data??[]
  const groups=useMemo(()=>{const map=new Map<string,Forecast[]>();forecasts.forEach(f=>map.set(f.resource_id,[...(map.get(f.resource_id)??[]),f]));return [...map.entries()]},[forecasts])
  return <><Heading title="Workload forecasts" description="Forecasts use historical simulated CPU observations and are cached for six hours." action={<button className="button button-primary" onClick={()=>void generate()} disabled={busy}>{busy?'Generating…':'Generate forecasts'}</button>}/><SimulatedBanner/><ErrorNotice error={error}/>{message&&<div className="card" style={{marginBottom:14,fontSize:12}}>{message}</div>}
    {loading?<Loading/>:groups.length===0?<div className="card"><Empty>No saved forecasts yet. Generate a forecast to start. Each eligible simulated resource is processed on demand.</Empty></div>:groups.map(([id,points])=><div className="card" key={id} style={{marginBottom:14}}><div className="panel-head"><h2 className="section-title">{id} · CPU forecast</h2><span className="badge badge-blue">{points[0].model}</span></div>
      <Line data={{labels:points.map(p=>dateLabel(p.timestamp)),datasets:[{label:'Prediction',data:points.map(p=>p.predicted),borderColor:'#2456e8',pointRadius:0,tension:.2},{label:'Lower bound',data:points.map(p=>p.lower_bound),borderColor:'#aebef5',borderDash:[4,4],pointRadius:0},{label:'Upper bound',data:points.map(p=>p.upper_bound),borderColor:'#aebef5',borderDash:[4,4],pointRadius:0}]}} options={{responsive:true,plugins:{legend:{position:'bottom'}},scales:{y:{min:0,max:100,ticks:{callback:v=>v+'%'}},x:{ticks:{maxTicksLimit:12}}}}}/>
    </div>)}</>
}

export function OptimizationPage() {
  const {data,reload,error,loading,setError}=useLoad<Recommendation[]>('/recommendations')
  const [busy,setBusy]=useState(false)
  const [message,setMessage]=useState('')
  const run=async()=>{setBusy(true);setError('');try{const r=await post<{recommendations:Recommendation[]}>('/recommendations/generate');setMessage('Generated '+r.recommendations.length+' new recommendations.');await reload()}catch(e){setError(e instanceof Error?e.message:'Could not analyze resources')}finally{setBusy(false)}}
  const request=async(id:string)=>{try{await post('/recommendations/'+encodeURIComponent(id)+'/request-action',{note:'Requested from dashboard'});await reload()}catch(e){setError(e instanceof Error?e.message:'Action request failed')}}
  return <><Heading title="Optimization" description="Review simulated idle and over-provisioned resources with estimated savings." action={<button className="button button-primary" disabled={busy} onClick={()=>void run()}>{busy?'Analyzing…':'Analyze resources'}</button>}/><SimulatedBanner/><ErrorNotice error={error}/>{message&&<div className="card" style={{marginBottom:14,fontSize:12}}>{message}</div>}
    {loading?<Loading/>:!data?.length?<div className="card"><Empty>No recommendations available. Run an analysis to inspect recent simulated telemetry.</Empty></div>:<div className="table-wrap"><table><thead><tr><th>Resource</th><th>Opportunity</th><th>Estimated monthly savings</th><th>Risk</th><th>Status</th><th>Details</th><th></th></tr></thead><tbody>{data.map(r=><tr key={r.id}><td>{r.resource_id}</td><td>{r.kind}</td><td>{money(r.estimated_monthly_savings_cents)}</td><td><span className={badgeClass(r.risk_level)}>{r.risk_level}</span></td><td><span className={badgeClass(r.status)}>{r.status}</span></td><td style={{whiteSpace:'normal',minWidth:300,maxWidth:450}}>{r.rationale}</td><td>{r.status==='pending'&&<button className="button" onClick={()=>void request(r.id)}>Request approval</button>}</td></tr>)}</tbody></table></div>}
  </>
}

export function ApprovalsPage() {
  const {data,reload,error,loading,setError}=useLoad<Action[]>('/actions')
  const decide=async(id:number,action:'approve'|'reject'|'execute')=>{try{await post('/actions/'+id+'/'+action,action==='reject'?{note:'Rejected in approval queue'}:{});await reload()}catch(e){setError(e instanceof Error?e.message:'Action failed')}}
  return <><Heading title="Approval queue" description="Every simulated infrastructure change requires an explicit approval."/><SimulatedBanner/><ErrorNotice error={error}/>
    {loading?<Loading/>:!data?.length?<div className="card"><Empty>No action requests are waiting.</Empty></div>:<div className="table-wrap"><table><thead><tr><th>ID</th><th>Recommendation</th><th>Action</th><th>Status</th><th>Requested</th><th>Controls</th></tr></thead><tbody>{data.map(a=><tr key={a.id}><td>#{a.id}</td><td>{a.recommendation_id}</td><td>{a.action}</td><td><span className={badgeClass(a.status)}>{a.status}</span></td><td>{new Date(a.requested_at).toLocaleString()}</td><td><div className="actions">{a.status==='pending'&&<><button className="button button-primary" onClick={()=>void decide(a.id,'approve')}>Approve</button><button className="button button-danger" onClick={()=>void decide(a.id,'reject')}>Reject</button></>}{a.status==='approved'&&<button className="button button-primary" onClick={()=>void decide(a.id,'execute')}>Execute simulated</button>}</div></td></tr>)}</tbody></table></div>}
  </>
}

type Policy = {name:string;enabled:boolean;paused:boolean;require_approval:boolean;max_monthly_savings_cents:number;allowed_actions:string[]}
export function PoliciesPage() {
  const {data,reload,error,loading,setError}=useLoad<Policy>('/policies/default')
  const [busy,setBusy]=useState(false)
  const change=async(enabled:boolean)=>{if(!data)return;setBusy(true);setError('');try{await put('/policies/default',{enabled,require_approval:true,max_monthly_savings_cents:data.max_monthly_savings_cents});await reload()}catch(e){setError(e instanceof Error?e.message:'Policy update failed')}finally{setBusy(false)}}
  return <><Heading title="Automation policy" description="Policy changes are recorded in the audit log and enforced by the API."/><SimulatedBanner/><ErrorNotice error={error}/>{loading?<Loading/>:data&&<div className="card" style={{maxWidth:680}}><div className="panel-head"><h2 className="section-title">Default simulated policy</h2><span className={data.enabled?'badge badge-green':'badge badge-amber'}>{data.enabled?'ENABLED':'PAUSED'}</span></div><p className="muted" style={{fontSize:12,lineHeight:1.7}}>This switch controls whether action requests and execution are permitted. Individual changes still need administrator approval.</p><div style={{margin:'22px 0'}}><div className="card-title">Allowed actions</div><p>{data.allowed_actions.join(' · ')}</p><div className="card-title">Maximum monthly savings per action</div><p>{money(data.max_monthly_savings_cents)}</p><div className="card-title">Approval required</div><p>Yes</p></div><button className={'button '+(data.enabled?'button-danger':'button-primary')} disabled={busy} onClick={()=>void change(!data.enabled)}>{busy?'Saving…':data.enabled?'Pause automation':'Resume automation'}</button></div>}</>
}

export function AuditPage() {
  const {data,error,loading}=useLoad<{id:number;user_id:number|null;event_type:string;entity_type:string;entity_id:string;details:Record<string,unknown>;created_at:string}[]>('/audit?limit=200')
  return <><Heading title="Audit history" description="Recorded sign-ins, policy changes, approvals, and simulated actions."/><SimulatedBanner/><ErrorNotice error={error}/>{loading?<Loading/>:<div className="table-wrap"><table><thead><tr><th>Time</th><th>Event</th><th>User</th><th>Entity</th><th>Details</th></tr></thead><tbody>{(data??[]).map(x=><tr key={x.id}><td>{new Date(x.created_at).toLocaleString()}</td><td>{x.event_type}</td><td>{x.user_id??'System'}</td><td>{x.entity_type} · {x.entity_id}</td><td style={{whiteSpace:'normal',maxWidth:450}}>{JSON.stringify(x.details)}</td></tr>)}</tbody></table>{!data?.length&&<Empty>No audit events recorded yet.</Empty>}</div>}</>
}

export function ReportsPage() {
  const {data,error,loading}=useLoad<{simulated:boolean;resource_count:number;running_count:number;monthly_cost_cents:number;pending_estimated_savings_cents:number;recommendations_by_status:Record<string,number>}>('/reports/summary')
  const [exportError,setExportError]=useState('')
  const [busy,setBusy]=useState(false)
  const download=async()=>{setBusy(true);setExportError('');try{const blob=await downloadReport();const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='automated-finops-simulated-report.csv';link.click();URL.revokeObjectURL(link.href)}catch(e){setExportError(e instanceof Error?e.message:'Report export failed')}finally{setBusy(false)}}
  const recommendationCount=Object.values(data?.recommendations_by_status??{}).reduce((total,value)=>total+value,0)
  return <><Heading title="Reports" description="Export simulated inventory and estimated savings for academic review." action={<button className="button button-primary" onClick={()=>void download()} disabled={!data||busy}>{busy?'Preparing…':'Export CSV'}</button>}/><SimulatedBanner/><ErrorNotice error={error||exportError}/>{loading?<Loading/>:<div className="card"><h2 className="section-title">Report contents</h2><p className="muted" style={{fontSize:12,lineHeight:1.8}}>The CSV includes resource category, current simulated status, estimated monthly run cost, optimization recommendation status, risk, and rationale. Currency is integer cents; all records are labeled simulated.</p><div className="grid grid-4"><StatCard label="Resources included" value={String(data?.resource_count??0)} detail="Local demo inventory"/><StatCard label="Running resources" value={String(data?.running_count??0)} detail="Included in current run rate"/><StatCard label="Estimated monthly cost" value={money(data?.monthly_cost_cents??0)} detail="Simulated running state"/><StatCard label="Pending recommendations" value={String(recommendationCount)} detail={money(data?.pending_estimated_savings_cents??0)+' estimated savings'}/></div></div>}</>
}

export function SettingsPage() { return <PoliciesPage/> }
