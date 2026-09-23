import { useEffect, useState } from 'react';
import { request } from '../../platform/client';
import { EmptyState, PageHeader, Panel } from '../../platform/ui';
import type { PlatformPageProps } from '../../platform/types';
import { historySchema, type Conversation, type PageWindow } from './contracts';
import { copy, label } from './catalog';

export function SavedAssistantPage(props: PlatformPageProps) {
 const {locale,revision,query,onNavigate}=props;
 const text=copy(locale);
 const [items,setItems]=useState<Conversation[]>([]);
 const [offset,setOffset]=useState(0);
 const [page,setPage]=useState<PageWindow>({total:0,limit:20,offset:0});
 const [loading,setLoading]=useState(true);
 const [error,setError]=useState(false);
 const legacyId=query.get('conversation_id');
 useEffect(()=>{if(legacyId)onNavigate('chat',{legacy_id:legacyId});},[legacyId,onNavigate]);
 useEffect(()=>{const controller=new AbortController();setLoading(true);setError(false);request(`/assistant/saved?offset=${offset}`,historySchema,{signal:controller.signal}).then(data=>{setItems(data.items);setPage(data);}).catch(error=>{if(error.name!=='AbortError')setError(true);}).finally(()=>{if(!controller.signal.aborted)setLoading(false);});return()=>controller.abort();},[revision,offset]);
 return <><PageHeader title={locale==='en'?'Saved conversations':'Conversaciones guardadas'} description={text.snapshotHelp}/>{loading?<p role="status">{text.loading}</p>:error?<p role="alert">{text.error}</p>:items.length===0?<EmptyState title={text.empty} description={locale==='en'?'Save a conversation in Argus to return to its dated answers.':'Guarda una conversación en Argus para volver a sus respuestas con fecha.'}/>:<div className="p-grid">{items.map(item=><Panel key={item.id}><h2>{label(text.actions,item.title)}</h2><p className="p-muted">{new Date(item.updated_at).toLocaleString(locale)} · {text[item.state]}</p><button className="p-button-secondary" type="button" onClick={()=>onNavigate('chat',{legacy_id:item.id})}>{locale==='en'?'Open conversation':'Abrir conversación'}</button></Panel>)}</div>}<div className="p-actions"><button className="p-button-secondary" disabled={loading||page.offset===0} onClick={()=>setOffset(Math.max(0,page.offset-page.limit))}>{text.previous}</button><span>{text.total}: {page.total}</span><button className="p-button-secondary" disabled={loading||page.offset+page.limit>=page.total} onClick={()=>setOffset(page.offset+page.limit)}>{text.next}</button></div></>;
}
