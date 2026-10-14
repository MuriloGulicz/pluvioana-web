"use strict";

const $ = (id) => document.getElementById(id);
const numberBR = new Intl.NumberFormat('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2});
const integerBR = new Intl.NumberFormat('pt-BR');
const dateFull = new Intl.DateTimeFormat('pt-BR', {day:'2-digit', month:'long', year:'numeric'});
const state = {dados: [], resultado: null, filtered: [], pagina: 1, ordenar: 'data', sentido: 'asc', buscando: false, consultaId: 0, abortController: null, installPrompt: null};

function localISO(d) {return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;}
function dateFromISO(iso) {return new Date(Number(iso.slice(0,4)), Number(iso.slice(5,7))-1, Number(iso.slice(8,10)));}
function brDate(iso) {return iso ? `${iso.slice(8,10)}/${iso.slice(5,7)}/${iso.slice(0,4)}` : '—';}
function minusDays(n){const d=new Date();d.setDate(d.getDate()-n);return localISO(d);}
function escapeCSV(v) {const s=String(v??'');return '"'+s.replaceAll('"','""')+'"';}

function init(){
  const hoje=localISO(new Date());
  $('dateTodayLabel').textContent=dateFull.format(new Date());
  $('inicio').max=hoje;$('fim').max=hoje;
  applyPeriod('30');
  $('consultaForm').addEventListener('submit', submitForm);
  $('clearBtn').addEventListener('click', reset);
  $('exportBtn').addEventListener('click', exportCSV);
  $('tableSearch').addEventListener('input',()=>{state.pagina=1;refreshTable();});
  $('pageSize').addEventListener('change',()=>{state.pagina=1;refreshTable();});
  $('prevPage').addEventListener('click',()=>{state.pagina--;refreshTable();});
  $('nextPage').addEventListener('click',()=>{state.pagina++;refreshTable();});
  for(const b of document.querySelectorAll('[data-period]')) b.addEventListener('click',()=>applyPeriod(b.dataset.period));
  for(const b of document.querySelectorAll('[data-key]')) b.addEventListener('click',()=>sortBy(b.dataset.key));
  for(const id of ['inicio','fim']) $(id).addEventListener('input',()=>{document.querySelectorAll('.quick-btn').forEach(b=>b.classList.remove('selected'));$('alertBox').hidden=true;});
  $('modo').addEventListener('change',updateSourceHint);
  $('installBtn').addEventListener('click',installApp);
  window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();state.installPrompt=event;$('installBtn').hidden=false;});
  window.addEventListener('appinstalled',()=>{$('installBtn').hidden=true;state.installPrompt=null;toast('PluvioANA instalado com sucesso.');});
  if('serviceWorker' in navigator){navigator.serviceWorker.register('/sw.js').catch(()=>{});}
  updateSourceHint();
  window.addEventListener('resize',throttle(()=>renderChart(),150));
}

function applyPeriod(p){
  let inicio,fim=localISO(new Date());
  const hoje=new Date();
  if(p==='mes'){inicio=localISO(new Date(hoje.getFullYear(),hoje.getMonth(),1));}
  else if(p==='anterior'){inicio=localISO(new Date(hoje.getFullYear(),hoje.getMonth()-1,1));fim=localISO(new Date(hoje.getFullYear(),hoje.getMonth(),0));}
  else {inicio=minusDays(Number(p)-1);}
  $('inicio').value=inicio;$('fim').value=fim;
  document.querySelectorAll('.quick-btn').forEach(b=>b.classList.toggle('selected', b.dataset.period===p));
  $('alertBox').hidden=true;
}
async function installApp(){
  if(!state.installPrompt){toast('Use o menu do navegador para instalar este aplicativo.');return;}
  await state.installPrompt.prompt();state.installPrompt=null;$('installBtn').hidden=true;
}
function updateSourceHint(){
  $('consistenciaField').hidden=$('modo').value!=='historico';
  $('sourceHint').innerHTML=$('modo').value==='historico'
    ? `<svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9"/><path d="M12 11v5m0-8h.01"/></svg> <span>A ANA fornece chuvas <b>diárias</b> nesta série. Sem horário individual: exibimos “—”, sem inventar medições.</span>`
    : `<svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9"/><path d="M12 11v5m0-8h.01"/></svg> <span>O serviço de telemetria é documentado para nível e vazão. Somente exibiremos chuva se o retorno tiver esse campo.</span>`;
}
function alertUser(text, kind='error'){
  const box=$('alertBox');box.className='alert '+(kind==='error'?'':kind);box.textContent=text;box.hidden=false;
}
function toast(text){const t=$('toast');t.textContent=text;t.classList.add('show');clearTimeout(toast.timer);toast.timer=setTimeout(()=>t.classList.remove('show'),3400);}
function setStatus(text,tag){$('statusText').innerHTML='<span class="live-dot"></span> ';$('statusText').append(document.createTextNode(text));$('originTag').textContent=tag;}
function loading(value){state.buscando=value;$('searchBtn').disabled=value;$('searchBtn').classList.toggle('is-loading',value);$('searchText').textContent=value?'Consultando ANA…':'Consultar dados';}
function reset(){
  if(state.abortController)state.abortController.abort();
  state.abortController=null;
  state.consultaId++;
  state.dados=[];state.resultado=null;state.filtered=[];state.pagina=1;state.ordenar='data';state.sentido='asc';
  $('estacao').value='';$('tableSearch').value='';$('modo').value='historico';$('consistencia').value='1';updateSourceHint();applyPeriod('30');
  $('alertBox').hidden=true;
  $('statTotal').textContent='0,00';$('statRecords').textContent='0';$('statRainDays').textContent='0';$('statMissing').textContent='0';
  $('exportBtn').disabled=true;loading(false);refreshTable();renderChart();setStatus('Filtros e resultados limpos. Pronto para uma nova consulta.','Aguardando consulta');toast('Formulário e resultados limpos.');
}
function validateForm(){
  const estacao=$('estacao').value.trim(), inicio=$('inicio').value, fim=$('fim').value, hoje=localISO(new Date());
  if(!/^\d{1,12}$/.test(estacao))throw new Error('Informe um código de estação válido, utilizando somente números.');
  if(!inicio||!fim)throw new Error('Preencha a data inicial e a data final.');
  if(inicio>fim)throw new Error('A data inicial não pode ser posterior à data final.');
  if(fim>hoje)throw new Error('O período não pode terminar em uma data futura.');
  if((dateFromISO(fim)-dateFromISO(inicio))/86400000>=1096)throw new Error('Consulte no máximo três anos por vez.');
  return {estacao,inicio,fim,modo:$('modo').value, consistencia:$('consistencia').value};
}
async function submitForm(ev){
  ev.preventDefault();if(state.buscando)return;
  let filtros;
  try{filtros=validateForm();}catch(e){alertUser(e.message);return;}
  const requestId=++state.consultaId;
  state.abortController=new AbortController();
  $('alertBox').hidden=true;loading(true);state.dados=[];state.resultado=null;state.pagina=1;$('tableSearch').value='';
  updateData({registros:[],resumo:{chuva_total_mm:0,total_registros:0,dias_com_chuva:0,sem_leitura:0}});
  setStatus('Aguarde. Consultando registros oficiais da ANA…','Consulta em andamento');
  try{
    const response=await fetch('/api/consultar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(filtros),signal:state.abortController.signal});
    const data=await response.json().catch(()=>{throw new Error('Resposta inesperada do servidor. Tente novamente.');});
    if(requestId!==state.consultaId)return;
    if(!response.ok)throw new Error(data.erro||'Não foi possível obter os dados.');
    state.resultado=data;
    updateData(data);
    if(!data.registros.length){
      const m=filtros.modo==='telemetria'
        ? 'A ANA não forneceu campos de precipitação para esta estação/intervalo. Esta operação costuma retornar apenas nível e vazão. Experimente “Chuvas diárias (histórico)”.'
        : 'A consulta foi concluída, mas não houve registros de chuva para a estação e o período selecionados. Verifique o código e a disponibilidade de dados da estação.';
      alertUser(m,'demo');setStatus('Consulta concluída, sem registros de precipitação.','ANA · Sem dados');
    }else{
      setStatus(`${integerBR.format(data.registros.length)} registros obtidos da ANA · ${brDate(filtros.inicio)} a ${brDate(filtros.fim)}.`,data.fonte);
      toast('Consulta concluída com sucesso.');
    }
  }catch(e){
    if(requestId!==state.consultaId)return;
    if(e.name==='AbortError'){setStatus('Consulta interrompida.','Cancelado');return;}
    alertUser(e.message||'Falha na comunicação com o serviço.');
    setStatus('Não foi possível concluir a consulta.','Falha na API');
  }finally{if(requestId===state.consultaId){state.abortController=null;loading(false);}}
}
function updateData(data){
  state.dados=data.registros||[];
  $('statTotal').textContent=numberBR.format(data.resumo?.chuva_total_mm??0);
  $('statRecords').textContent=integerBR.format(data.resumo?.total_registros??0);
  $('statRainDays').textContent=integerBR.format(data.resumo?.dias_com_chuva??0);
  $('statMissing').textContent=integerBR.format(data.resumo?.sem_leitura??0);
  $('exportBtn').disabled=state.dados.length===0;
  refreshTable();renderChart();
}
function sortBy(key){
  if(state.ordenar===key)state.sentido=state.sentido==='asc'?'desc':'asc';
  else{state.ordenar=key;state.sentido=key==='chuva_mm'?'desc':'asc';}
  state.pagina=1;refreshTable();
}
function currentFiltered(){
  const term=$('tableSearch').value.trim().toLowerCase();
  let list=state.dados.filter(r=>{
    if(!term)return true;
    const busca=`${r.estacao} ${brDate(r.data)} ${r.hora||''} ${r.chuva_mm===null?'sem leitura':numberBR.format(r.chuva_mm)}`.toLowerCase();
    return busca.includes(term);
  });
  const key=state.ordenar, sign=state.sentido==='asc'?1:-1;
  return list.sort((a,b)=>{
    if(key==='chuva_mm'){return ((a[key]===null?Number.NEGATIVE_INFINITY:a[key])-(b[key]===null?Number.NEGATIVE_INFINITY:b[key]))*sign;}
    return String(a[key]??'').localeCompare(String(b[key]??''),'pt-BR',{numeric:true})*sign;
  });
}
function el(tag,className,text){const e=document.createElement(tag);if(className)e.className=className;if(text!==undefined)e.textContent=text;return e;}
function emptyTable(message){const tr=el('tr'),td=el('td','empty-table');td.colSpan=5;td.append(el('div','empty-icon','☔'),el('strong','',message),el('span','','Altere os filtros ou realize uma nova consulta.'));tr.append(td);return tr;}
function refreshTable(){
  const list=currentFiltered();state.filtered=list;
  const size=Number($('pageSize').value),pages=Math.max(1,Math.ceil(list.length/size));
  state.pagina=Math.max(1,Math.min(pages,state.pagina));
  const start=(state.pagina-1)*size,shown=list.slice(start,start+size),body=$('tableBody');body.replaceChildren();
  if(!shown.length)body.append(emptyTable(state.dados.length?'Nenhum registro corresponde ao filtro.':'Nenhum registro para exibir.'));
  else for(const r of shown){
    const tr=el('tr');tr.append(el('td','station-id',r.estacao),el('td','',brDate(r.data)),el('td','',r.hora||'—'));
    const chuva=el('td','rain-number'+(r.chuva_mm===null||r.chuva_mm===0?' rain-zero':''),r.chuva_mm===null?'—':numberBR.format(r.chuva_mm));
    tr.append(chuva);
    const status=el('td','condition');status.append(el('span','tag '+(r.chuva_mm===null?'tag-missing':r.chuva_mm>0?'tag-ok':'tag-zero'),r.chuva_mm===null?'Sem leitura':r.chuva_mm>0?'Com chuva':'Sem chuva'));
    tr.append(status);body.append(tr);
  }
  $('countBadge').textContent=integerBR.format(list.length);
  $('tableInfo').textContent=list.length?`Exibindo ${integerBR.format(start+1)}–${integerBR.format(Math.min(start+size,list.length))} de ${integerBR.format(list.length)} registros`:'Nenhum registro';
  $('pageLabel').textContent=`${state.pagina} / ${pages}`;
  $('prevPage').disabled=state.pagina===1;$('nextPage').disabled=state.pagina===pages;
  for(const b of document.querySelectorAll('.sort-btn span'))b.textContent='↕';
  const selected=document.querySelector(`.sort-btn[data-key="${state.ordenar}"] span`);
  if(selected)selected.textContent=state.sentido==='asc'?'↑':'↓';
}
function groupDays(){
  const acumulado=new Map();
  // "Sem leitura" não pode virar uma barra de 0 mm.
  for(const r of state.dados){
    if(r.chuva_mm===null || r.chuva_mm===undefined)continue;
    acumulado.set(r.data,(acumulado.get(r.data)||0)+r.chuva_mm);
  }
  const ordered=[...acumulado].sort(([a],[b])=>a.localeCompare(b));
  if(!ordered.length)return [];
  const first=state.resultado?.inicio || ordered[0][0];
  const last=state.resultado?.fim || ordered[ordered.length-1][0];
  const elapsed=Math.round((dateFromISO(last)-dateFromISO(first))/86400000)+1;
  const useMonth=elapsed>180,useWeek=elapsed>45;
  const buckets=new Map();
  for(const [iso,value] of ordered){
    let key,label;
    if(useMonth){key=iso.slice(0,7);label=iso.slice(5,7)+'/'+iso.slice(2,4);}
    else if(useWeek){const d=dateFromISO(iso);d.setDate(d.getDate()-(d.getDay()+6)%7);key=localISO(d);label=`${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}`;}
    else{key=iso;label=iso.slice(8,10)+'/'+iso.slice(5,7);}
    if(!buckets.has(key))buckets.set(key,{label,value:0});
    buckets.get(key).value+=value;
  }
  return [...buckets.values()];
}
const ns='http://www.w3.org/2000/svg';
function svgEl(tag,attrs,txt){const node=document.createElementNS(ns,tag);for(const[k,v]of Object.entries(attrs||{}))node.setAttribute(k,String(v));if(txt!==undefined)node.textContent=txt;return node;}
function renderChart(){
  const target=$('chart');target.replaceChildren();
  const bars=groupDays();
  if(!bars.length){$('chartSubtitle').textContent='Visualize a intensidade da precipitação no período consultado.';const e=el('div','chart-empty');const icon=svgEl('svg',{viewBox:'0 0 24 24',fill:'none'});icon.append(svgEl('path',{d:'M4 19V5m0 14h17M9 16v-5m5 5V7m5 9v-8'}));e.append(icon,el('strong','',state.dados.length?'Sem dados válidos para o gráfico':'Seu gráfico aparecerá aqui'),el('span','',state.dados.length?'A consulta retornou apenas leituras ausentes.':'Consulte uma estação para visualizar a distribuição da chuva.'));target.append(e);return;}
  const width=1000,height=218,left=44,top=18,bottom=33,right=14,chartHeight=height-top-bottom,chartWidth=width-left-right;
  const max=Math.max(...bars.map(b=>b.value),.1),upper=max*1.22;
  const svg=svgEl('svg',{viewBox:`0 0 ${width} ${height}`,preserveAspectRatio:'none',class:'rain-chart',role:'img','aria-label':'Gráfico de barras de chuva por período'});
  const defs=svgEl('defs'),gradient=svgEl('linearGradient',{id:'rainGradient',x1:'0%',y1:'0%',x2:'0%',y2:'100%'});gradient.append(svgEl('stop',{offset:'0%','stop-color':'#2397e4'}),svgEl('stop',{offset:'100%','stop-color':'#82d0f7'}));defs.append(gradient);svg.append(defs);
  for(let i=0;i<=4;i++){
    const y=top+chartHeight*(i/4),v=(upper*(4-i)/4);
    svg.append(svgEl('line',{x1:left,y1:y,x2:width-right,y2:y,class:'gridline'}));
    svg.append(svgEl('text',{x:left-9,y:y+4,'text-anchor':'end'},numberBR.format(v)));
  }
  const slot=chartWidth/bars.length,barWidth=Math.max(3,Math.min(32,slot*.62)),step=Math.max(1,Math.ceil(bars.length/16));
  bars.forEach((b,i)=>{
    const x=left+i*slot+(slot-barWidth)/2;
    const h=chartHeight*(b.value/upper),y=top+chartHeight-h;
    const r=svgEl('rect',{class:'bar',x,y,width:barWidth,height:Math.max(1,h),rx:Math.min(3,barWidth/3),fill:'url(#rainGradient)'});
    r.append(svgEl('title',{},`${b.label}: ${numberBR.format(b.value)} mm`));svg.append(r);
    if(i%step===0)svg.append(svgEl('text',{x:left+i*slot+slot/2,y:height-10,'text-anchor':'middle'},b.label));
  });
  target.append(svg);
  $('chartSubtitle').textContent=bars.length>1?`Distribuição em ${bars.length} intervalos; soma de todas as leituras disponíveis.`:'Distribuição da precipitação registrada.';
}
function exportCSV(){
  if(!state.filtered.length){toast('Não há dados filtrados para exportar.');return;}
  const resultado=state.resultado;
  const prefix='\uFEFF';
  const linhas=[['Código da estação','Data','Hora','Chuva (mm)']];
  for(const r of state.filtered)linhas.push([r.estacao,brDate(r.data),r.hora||'',r.chuva_mm===null?'':numberBR.format(r.chuva_mm)]);
  const csv=prefix+linhas.map(r=>r.map(escapeCSV).join(';')).join('\r\n')+'\r\n';
  const blob=new Blob([csv],{type:'text/csv;charset=utf-8;'}),url=URL.createObjectURL(blob);
  const a=document.createElement('a');a.href=url;
  a.download=`chuva_ANA_${resultado.estacao}_${resultado.inicio.replaceAll('-','')}_${resultado.fim.replaceAll('-','')}.csv`;
  document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),2000);
  toast(`${integerBR.format(state.filtered.length)} registros exportados para CSV.`);
}
function throttle(fn,ms){let id;return(...args)=>{clearTimeout(id);id=setTimeout(()=>fn(...args),ms);};}
window.addEventListener('DOMContentLoaded',init);
