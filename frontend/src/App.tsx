import { useEffect, useState, type FormEvent } from 'react'
import { Link, Navigate, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { Activity, Bell, Boxes, CircleDollarSign, ClipboardCheck, FileBarChart2, Gauge, LogOut, Settings2, ShieldCheck, Sparkles } from 'lucide-react'
import { api, post, setToken } from './services/api'
import type { User } from './types'
import { ApprovalsPage, AuditPage, DashboardPage, ErrorNotice, ForecastsPage, OptimizationPage, PoliciesPage, ReportsPage, ResourcesPage, SettingsPage } from './Pages'

const nav = [
  {to:'/', label:'Overview', icon:Gauge, group:'MONITOR'},
  {to:'/resources', label:'Resources', icon:Boxes, group:'MONITOR'},
  {to:'/forecasts', label:'Forecasts', icon:Activity, group:'OPTIMIZE'},
  {to:'/optimization', label:'Recommendations', icon:Sparkles, group:'OPTIMIZE'},
  {to:'/approvals', label:'Approval queue', icon:ClipboardCheck, group:'GOVERN'},
  {to:'/policies', label:'Automation policy', icon:ShieldCheck, group:'GOVERN'},
  {to:'/audit', label:'Audit history', icon:Bell, group:'GOVERN'},
  {to:'/reports', label:'Reports', icon:FileBarChart2, group:'REPORTS'},
  {to:'/settings', label:'Settings', icon:Settings2, group:'REPORTS'},
]
const titles:Record<string,string> = {'/':'Overview','/resources':'Resources','/forecasts':'Forecasts','/optimization':'Recommendations','/approvals':'Approval queue','/policies':'Automation policy','/audit':'Audit history','/reports':'Reports','/settings':'Settings'}

function Login({ onLogin }: {onLogin:(user:User)=>void}) {
  const [email,setEmail]=useState('admin@finops.local')
  const [password,setPassword]=useState('Admin123!')
  const [error,setError]=useState('')
  const [busy,setBusy]=useState(false)
  const submit=async(event:FormEvent)=>{
    event.preventDefault();setBusy(true);setError('')
    try{const result=await post<{access_token:string;user:User}>('/auth/login',{email,password});setToken(result.access_token);onLogin(result.user)}
    catch(e){setError(e instanceof Error?e.message:'Sign in failed')}
    finally{setBusy(false)}
  }
  return <main className="login-page"><section className="login-card">
    <div className="brand" style={{padding:0}}><span className="brand-mark"><CircleDollarSign size={20}/></span><span>Automated FinOps</span></div>
    <h1>Welcome back</h1><p>Sign in to review your local cloud cost simulation and optimization workflow.</p>
    <ErrorNotice error={error}/>
    <form onSubmit={submit}>
      <div className="field"><label htmlFor="email">Email</label><input id="email" type="email" value={email} onChange={e=>setEmail(e.target.value)} required/></div>
      <div className="field"><label htmlFor="password">Password</label><input id="password" type="password" value={password} onChange={e=>setPassword(e.target.value)} required/></div>
      <button className="button button-primary" style={{width:'100%',padding:11,marginTop:7}} disabled={busy}>{busy?'Signing in…':'Sign in'}</button>
    </form>
    <p style={{fontSize:11,marginTop:18}}>Demo admin: <strong>admin@finops.local</strong> · <strong>Admin123!</strong></p>
  </section></main>
}

function Shell({user,onLogout}:{user:User;onLogout:()=>void}) {
  const location=useLocation()
  const activeTitle=titles[location.pathname]??'Automated FinOps'
  const groups=[...new Set(nav.map(x=>x.group))]
  return <div className="app-shell">
    <aside className="sidebar">
      <Link to="/" className="brand" style={{color:'inherit',textDecoration:'none'}}><span className="brand-mark"><CircleDollarSign size={19}/></span><span>Automated FinOps</span></Link>
      {groups.map(group=><div className="nav-group" key={group}><div className="nav-label">{group}</div>{nav.filter(x=>x.group===group).map(item=>{const Icon=item.icon;return <NavLink key={item.to} to={item.to} end={item.to==='/'} className={({isActive})=>'nav-link'+(isActive?' active':'')}><Icon size={16}/>{item.label}</NavLink>})}</div>)}
      <div className="side-note"><strong>Local simulation</strong><br/>All resources, metrics, forecasts, and cost savings are generated demo data.</div>
    </aside>
    <section className="main-area"><header className="topbar"><div className="top-title">{activeTitle}</div><div className="top-user"><span>{user.display_name} · {user.role}</span><span className="avatar">{user.display_name.slice(0,1).toUpperCase()}</span><button className="button" aria-label="Sign out" onClick={onLogout}><LogOut size={14}/>Sign out</button></div></header>
      <main className="content"><Routes>
        <Route path="/" element={<DashboardPage/>}/><Route path="/resources" element={<ResourcesPage/>}/>
        <Route path="/forecasts" element={<ForecastsPage role={user.role}/>}/><Route path="/optimization" element={<OptimizationPage role={user.role}/>}/>
        <Route path="/approvals" element={<ApprovalsPage role={user.role}/>}/><Route path="/policies" element={<PoliciesPage role={user.role}/>}/>
        <Route path="/audit" element={<AuditPage/>}/><Route path="/reports" element={<ReportsPage/>}/>
        <Route path="/settings" element={<SettingsPage role={user.role}/>}/><Route path="*" element={<Navigate to="/" replace/>}/>
      </Routes></main>
    </section>
  </div>
}

export default function App() {
  const [user,setUser]=useState<User|null>(null)
  const [checking,setChecking]=useState(true)
  const navigate=useNavigate()
  useEffect(()=>{
    if(!localStorage.getItem('finops_token')){setChecking(false);return}
    void api<User>('/auth/me').then(setUser).catch(()=>{setToken(null);setUser(null)}).finally(()=>setChecking(false))
  },[])
  const logout=()=>{setToken(null);setUser(null);navigate('/')}
  if(checking)return <div className="login-page"><div className="card">Connecting to local API…</div></div>
  if(!user)return <Login onLogin={setUser}/>
  return <Shell user={user} onLogout={logout}/>
}
