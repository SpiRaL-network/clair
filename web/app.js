'use strict';
const $ = id => document.getElementById(id);
let selected = null, current = null, state = null, tab = 'summary', busy = false, lastContent = '';
let participantsKey = '', voicesKey = '', voiceOptionsReady = false, voiceMeetingId = null, referencesKey = '';
let importFile = null, modelCatalogKey = '', modelOptionsKey = '', modelMeetingId = null, executionDefault = null;
const labels = {done:'Terminé',queued:'En attente',preparing:'Préparation',transcribing:'Transcription',summarizing:'Résumé en cours',diarizing:'Analyse des voix',recording:'Enregistrement',error:'À vérifier',cancelled:'Annulé',interrupted:'Interrompu'};
const running = s => ['queued','preparing','transcribing','summarizing','diarizing'].includes(s);
const date = t => new Date(t*1000).toLocaleDateString('fr-FR',{day:'numeric',month:'long',year:'numeric'});
const time = sec => { sec=Math.max(0,Math.floor(sec));return [Math.floor(sec/3600),Math.floor(sec/60)%60,sec%60].map(x=>String(x).padStart(2,'0')).join(':'); };
function node(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;}
function toast(message,error=false){$('toast').textContent=message;$('toast').className=error?'error':'';$('toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').hidden=true,error?9000:3500);}
async function api(path,method='GET',data){const res=await fetch('/api/'+path,{method,headers:{'Content-Type':'application/json','X-Clair-Token':window.CLAIR_TOKEN},body:data===undefined?undefined:JSON.stringify(data)});let value;try{value=await res.json();}catch{throw new Error('Réponse inattendue du service local.');}if(!res.ok)throw new Error(typeof value.detail==='string'?value.detail:'La demande n’a pas pu aboutir.');return value;}
async function action(fn){if(busy)return;busy=true;try{await fn();await refresh();}catch(e){toast(e.message,true);}finally{busy=false;}}
function view(name){for(const v of ['home','record','meeting','models'])$(v+'-view').hidden=v!==name;$('nav-home').classList.toggle('active',name==='home'||name==='meeting');$('nav-record').classList.toggle('active',name==='record');$('nav-models').classList.toggle('active',name==='models');if(name!=='meeting'){selected=null;current=null;lastContent='';}window.scrollTo(0,0);}
function badge(status){return node('span','status-badge'+(running(status)||status==='recording'?' busy':['error','interrupted','cancelled'].includes(status)?' error':''),labels[status]||status);}
const gigabytes = n => (n/1e9).toLocaleString('fr-FR',{maximumFractionDigits:2})+' Go';
function modelOptions(select, preferred){const old=preferred||select.value;select.replaceChildren();for(const m of state.catalog.models.filter(m=>m.installed)){const o=node('option','',m.name);o.value=m.id;select.append(o);}if(!select.options.length){const o=node('option','','Installez un modèle dans le catalogue');o.value='';select.append(o);}select.value=[...select.options].some(o=>o.value===old)?old:state.catalog.default;if(select.selectedIndex<0)select.selectedIndex=0;}
function updateModels(){
  if(!state?.catalog)return;
  const c=state.catalog,r=c.refresh;
  $('auto-catalog').checked=c.auto_catalog;
  $('refresh-catalog').disabled=r.status==='refreshing';
  $('catalog-status').textContent=r.message+(r.checked_at?' Dernière actualisation : '+new Date(r.checked_at*1000).toLocaleString('fr-FR')+'.':'');
  const engine=state.voice_engine,d=engine.download,installing=d&&d.status==='downloading';
  $('install-voices').disabled=!!installing;
  $('install-voices').textContent=installing?'Installation…':engine.installed?'Réinstaller les modèles de voix':'Installer les modèles de voix';
  $('voice-install-status').textContent=(d?d.message+(installing?' '+Math.round(d.progress)+' %':''):engine.installed?'Modèles installés':'À installer · 34 Mo')+(engine.installed?(engine.gpu_available?' · GPU NVIDIA et CPU disponibles':' · CPU disponible'):'');
  $('cancel-voice-install').hidden=!installing;
  for(const id of ['import-diarize','record-diarize']){
    $(id).disabled=!engine.installed||state.recording.active||!!state.active;
    if(!voiceOptionsReady)$(id).checked=engine.installed;
  }
  voiceOptionsReady=true;
  const optionsKey=JSON.stringify([c.default,c.models.map(m=>[m.id,m.installed])]);
  if(modelOptionsKey!==optionsKey){modelOptionsKey=optionsKey;for(const id of ['import-model','record-model','summary-model'])modelOptions($(id));}
  if(executionDefault!==c.execution){executionDefault=c.execution;for(const id of ['import-execution','record-execution','default-execution','import-voice-execution','record-voice-execution'])$(id).value=c.execution;}
  const query=$('model-search').value.toLocaleLowerCase('fr');
  const key=JSON.stringify([c,query]);if(key===modelCatalogKey)return;modelCatalogKey=key;
  const grid=$('models-grid');grid.replaceChildren();
  const download=c.download,downloading=download&&['downloading','verifying'].includes(download.status);
  $('model-download').hidden=!download;
  if(download){const m=c.models.find(x=>x.id===download.model_id);$('model-download-message').textContent=(m?m.name+' · ':'')+download.message;$('model-download-fill').style.width=Math.min(100,download.progress)+'%';$('model-download-size').textContent=gigabytes(download.received)+' / '+gigabytes(download.total);$('cancel-download').hidden=!downloading;}
  const matches=c.models.filter(m=>[m.name,m.repo,m.license||''].join(' ').toLocaleLowerCase('fr').includes(query));
  matches.sort((a,b)=>Number(b.installed)-Number(a.installed)||(b.release_date||'').localeCompare(a.release_date||''));
  if(!matches.length)grid.append(node('p','input-note','Aucun modèle trouvé.'));
  for(const m of matches){
    const preferred=m.id===c.default,card=node('article','model-card'+(preferred?' preferred':'')),top=node('div','model-tags');
    top.append(node('span','',preferred?'Par défaut':m.installed?'Installé':m.dynamic?'Nouveauté découverte':'À télécharger'));
    if(m.release_date)top.append(node('span','',(m.date_label?m.date_label+' : ':'')+new Date(m.release_date+'T12:00:00').toLocaleDateString('fr-FR',{day:'numeric',month:'long',year:'numeric'})));
    card.append(top,node('h2','',m.name),node('p','',m.description));
    const tags=node('div','model-tags');tags.append(node('span','',gigabytes(m.size)),node('span','',m.quantization),node('span','','Mémoire ≈ '+m.memory_gb+' Go'));
    if(m.dynamic)tags.append(node('span','',m.repo.split('/')[0]),node('span','',m.license),node('span','','Compatibilité à essayer'));
    card.append(tags);
    const row=node('div','model-actions'),b=node('button',m.installed?'secondary':'primary',m.installed?(preferred?'Modèle par défaut':'Utiliser par défaut'):(downloading&&download.model_id===m.id?'En cours…':m.partial_bytes?'Reprendre le téléchargement':'Télécharger'));
    b.disabled=m.installed?preferred:!!downloading;
    b.onclick=()=>action(async()=>{if(m.installed){await api('models/'+m.id+'/default','POST',{});for(const id of ['import-model','record-model'])if(!$(id).disabled)$(id).value=m.id;toast('Modèle par défaut enregistré.');}else await api('models/'+m.id+'/download','POST',{});});
    const a=node('a','','Fiche du modèle ↗');a.href=m.source;a.target='_blank';a.rel='noopener noreferrer';row.append(b,a);card.append(row);grid.append(card);
  }
}

function updateMeetingModel(m){const locked=!!state.active||state.recording.active;$('summary-model').disabled=locked;$('summary-execution').disabled=locked;if(modelMeetingId!==m.id){modelMeetingId=m.id;modelOptions($('summary-model'),m.llm_model);$('summary-execution').value=m.execution||'auto';}const model=m.report?.model?.name||state.catalog.models.find(x=>x.id===m.report_model)?.name||(m.report?'Qwen2.5 14B Instruct (version précédente)':'');$('report-model').textContent=model?'Compte rendu actuel : '+model+(m.summary_device?' · '+m.summary_device.toUpperCase():''):'';}
function renderLibrary(){const lib=$('library'),history=$('history');lib.replaceChildren();history.replaceChildren();const meetings=state.meetings;$('meeting-count').textContent=meetings.length+' réunion'+(meetings.length>1?'s':'');if(!meetings.length){lib.append(node('div','empty','Vos prochains comptes rendus vous attendront ici.'));}meetings.forEach((m,i)=>{const row=node('button','library-row');row.append(node('div','file-icon','▤'));const title=node('div','row-title');title.append(node('strong','',m.title),node('small','',date(m.created)+(m.duration?' · '+Math.ceil(m.duration/60)+' min':'')));row.append(title,badge(m.status),node('span','row-arrow','↗'));row.onclick=()=>m.status==='recording'?showRecord():openMeeting(m.id);lib.append(row);if(i<8){const h=node('button','history-item');h.append(node('strong','',m.title),node('small','',date(m.created)));h.onclick=row.onclick;history.append(h);}});}
async function refresh(){try{state=await api('state');renderLibrary();updateModels();updateCapture();$('show-import').disabled=!!state.active||state.recording.active;$('start-record').disabled=!!state.active||state.recording.active;if(selected){const m=await api('meetings/'+selected);renderMeeting(m);}}catch(e){if(!$('toast').hidden)return;toast('Le service local ne répond plus. Relancez Clair si nécessaire.',true);}}
async function showRecord(){view('record');try{const d=await api('devices');const sys=$('system-device'),mic=$('mic-device');sys.replaceChildren();mic.replaceChildren();for(const x of d.system){const o=node('option','',x.name.replace(' [Loopback]',''));o.value=x.id;sys.append(o);}for(const x of d.microphones){const o=node('option','',x.name);o.value=x.id;mic.append(o);}const none=node('option','','Sans microphone');none.value='';mic.append(none);if(d.default_system!==null)sys.value=d.default_system;if(d.default_mic!==null)mic.value=d.default_mic;if(!d.system.length)toast('Aucune sortie audio compatible détectée. Branchez un casque ou des haut-parleurs.',true);updateCapture();}catch(e){toast(e.message,true);}}
function updateCapture(){if(!state)return;const r=state.recording;$('record-state').textContent=r.active?'Enregistrement en cours':'Prêt à enregistrer';$('record-indicator').classList.toggle('live',r.active);$('record-timer').textContent=time(r.seconds);$('system-level').style.width=Math.round(r.levels.system*100)+'%';$('mic-level').style.width=Math.round(r.levels.mic*100)+'%';$('start-record').hidden=r.active;$('stop-record').hidden=!r.active;for(const id of ['record-title','system-device','mic-device','record-language','record-context','record-model','record-execution','record-participants','record-speaker-count','record-voice-execution'])$(id).disabled=r.active;$('record-warning').textContent=!r.healthy?'Une source audio s’est arrêtée. Arrêtez et vérifiez vos périphériques.':r.errors.length?'Des interruptions audio ont été signalées. Vérifiez l’enregistrement.':'Les indicateurs s’animent lorsque du son est capturé.';}
async function openMeeting(id){view('meeting');selected=id;modelMeetingId=null;participantsKey='';voicesKey='';tab='summary';lastContent='';$('audio').pause();$('audio').removeAttribute('src');await refresh();}
function seek(ts){const audio=$('audio');audio.ontimeupdate=null;if(!audio.src)return;audio.currentTime=typeof ts==='number'?ts:ts.split(':').reduce((a,b)=>a*60+Number(b),0);audio.play().catch(()=>{});}
function evidence(n,quote){if(quote)n.title='Extrait original : '+quote;return n;}
function timeButton(ts){const b=node('button','time-link',typeof ts==='number'?time(ts):ts);b.onclick=()=>seek(ts);return b;}
function empty(container,title,text){const p=node('div','placeholder');p.append(node('strong','',title),node('span','',text));container.append(p);}
function renderMeeting(m){current=m;updateParticipants(m);updateMeetingModel(m);$('meeting-title').textContent=m.title;$('meeting-date').textContent=date(m.created).toUpperCase();$('meeting-meta').textContent=(m.duration?Math.ceil(m.duration/60)+' minute'+(Math.ceil(m.duration/60)>1?'s':'')+' · ':'')+(m.device==='cuda'?'Transcription GPU NVIDIA · ':m.device==='cpu'?'Transcription CPU · ':'')+'Conservé sur votre PC';const b=badge(m.status);$('detail-status').className=b.className;$('detail-status').textContent=b.textContent;const isRunning=running(m.status);$('progress-panel').hidden=!isRunning;$('progress-message').textContent=m.message;$('progress-fill').style.width=m.progress+'%';$('cancel-job').disabled=state.active!==m.id;$('generate-summary').disabled=!m.segments.length||!!state.active||state.recording.active;$('generate-summary').textContent=m.report?'✦ Refaire le résumé':'✦ Générer le résumé';$('segment-count').textContent=m.segments.length;$('error-panel').hidden=!['error','interrupted','cancelled'].includes(m.status);if(!$('error-panel').hidden){$('error-panel').replaceChildren(node('div','',m.message));const summaryOnly=m.failed_stage==='summary'&&m.segments.length>0;const retry=node('button','secondary',summaryOnly?'Reprendre le résumé':'Relancer la transcription');retry.disabled=!!state.active||state.recording.active;retry.onclick=()=>action(()=>api('meetings/'+m.id+'/retry','POST',summaryOnly?{summary_only:true,llm_model:$('summary-model').value,execution:$('summary-execution').value}:{summary_only:false}));$('error-panel').append(retry);}
const audio=$('audio'),source=location.origin+'/api/meetings/'+m.id+'/audio';if(m.duration&&audio.src!==source){audio.src=source;audio.load();}document.querySelector('.audio-panel').hidden=!m.duration;
const key=JSON.stringify([m.id,m.report,m.segments.map(s=>[s.start,s.text,s.speaker,s.voice,s.voice_uncertain]),m.status,m.report_stale,m.participants,!!state.active,state.recording.active]);if(key!==lastContent){lastContent=key;renderSummary(m);renderTranscript();}setTab(tab);}
function renderSummary(m){const c=$('summary-content');c.replaceChildren();if(!m.report){empty(c,running(m.status)?'L’essentiel prend forme.':'Votre compte rendu apparaîtra ici.',running(m.status)?'Vous pouvez déjà consulter la transcription pendant le traitement.':'Générez un résumé à partir de la transcription disponible.');return;}const r=m.report;const overview=node('div','summary-overview');overview.append(node('div','eyebrow','EN QUELQUES MOTS'),node('p','',r.overview));if(r.participants?.length)overview.append(node('p','input-note','Participants déclarés : '+r.participants.join(', ')));c.append(overview);if(r.topics?.length){const topics=node('div','summary-grid');r.topics.forEach(t=>{const panel=node('section','summary-section');panel.append(node('h2','',t.title));t.points.forEach(p=>panel.append(node('p','decision-item','• '+p)));topics.append(panel);});c.append(topics);}const grid=node('div','summary-grid'),decisions=node('section','summary-section'),questions=node('section','summary-section');decisions.append(node('h2','','Décisions prises'));if(!r.decisions.length)decisions.append(node('p','input-note','Aucune décision explicite identifiée.'));r.decisions.forEach(d=>{const row=node('div','decision-item'),text=node('div','',d.text);if(d.time)text.append(evidence(timeButton(d.time),d.quote));row.append(node('span','check-icon','✓'),text);decisions.append(row);});questions.append(node('h2','','Questions ouvertes'));if(!r.questions.length)questions.append(node('p','input-note','Aucune question ouverte identifiée.'));r.questions.forEach(q=>questions.append(node('p','decision-item','↳ '+q)));grid.append(decisions,questions);c.append(grid);if(r.proposals?.length){const proposals=node('section','summary-section');proposals.append(node('h2','','Propositions à confirmer'));r.proposals.forEach(d=>{const row=node('p','decision-item',d.text);if(d.time)row.append(evidence(timeButton(d.time),d.quote));proposals.append(row);});c.append(proposals);}const actions=node('section','summary-section');actions.append(node('h2','','Prochaines étapes'));if(!r.actions.length)actions.append(node('p','input-note','Aucune action explicite identifiée.'));else{const table=node('table','action-table'),head=node('tr','');['ACTION','RESPONSABLE','ÉCHÉANCE','REPÈRE'].forEach(x=>head.append(node('th','',x)));const thead=node('thead','');thead.append(head);table.append(thead);const body=node('tbody','');r.actions.forEach(a=>{const row=node('tr','');[a.task,a.owner,a.due].forEach(x=>row.append(node('td','',x)));const t=node('td','');if(a.time)t.append(evidence(timeButton(a.time),a.quote));else t.textContent='—';row.append(t);body.append(row);});table.append(body);actions.append(table);}c.append(actions);if(m.capture_warnings?.length)c.append(node('p','summary-note','La capture a signalé des interruptions audio. Vérifiez les passages concernés.'));c.append(node('p','summary-note','Compte rendu généré par IA. Vérifiez les décisions, noms, chiffres et attributions dans la transcription. Les repères permettent de réécouter les passages cités.'));}
const segmentDisplay=s=>(s.speaker?s.speaker+' : ':s.voice?'Voix '+s.voice.split('-')[1]+' (non confirmée) : ':'')+s.text;
function speakerOptions(select, names, selected){
  select.append(node('option','','Non attribué'));
  select.options[0].value='';
  for(const name of names){const o=node('option','',name);o.value=name;select.append(o);}
  select.value=selected||'';
}
function updateParticipants(m){
  const locked=!!state.active||state.recording.active,key=JSON.stringify([m.id,m.participants]);
  if(participantsKey!==key){participantsKey=key;$('meeting-participants').value=(m.participants||[]).join('\n');participantHint('meeting',true);}
  if(voiceMeetingId!==m.id){voiceMeetingId=m.id;$('meeting-voice-execution').value=m.voice_execution||m.execution||'auto';}
  $('voice-device').textContent=m.voice_device?'Dernière analyse : '+(m.voice_device==='cuda'?'GPU NVIDIA':'CPU'):'';
  if(document.activeElement!==$('meeting-speaker-count'))$('meeting-speaker-count').value=m.speaker_count||0;
  for(const id of ['meeting-participants','save-participants','meeting-speaker-count','meeting-voice-execution'])$(id).disabled=locked;
  updateReferences(m, locked);
  $('detect-voices').disabled=locked||!m.segments.length||!state.voice_engine.installed;
  $('retranscribe').disabled=locked||!m.segments.length;
  $('detect-voices').textContent=m.voices?.length?'Réanalyser les voix':'Distinguer les voix';
  $('report-stale').hidden=!m.report_stale;
  const vkey=JSON.stringify([m.id,m.voices,m.participants,locked]);
  if(vkey===voicesKey)return;voicesKey=vkey;
  const list=$('voice-list');list.replaceChildren();
  if(!m.voices?.length){list.append(node('p','input-note',state.voice_engine.installed?'Lancez la détection pour obtenir des voix à nommer.':'Installez les modèles de voix depuis le catalogue. Vous pouvez déjà attribuer les passages manuellement dans la transcription.'));return;}
  for(const v of m.voices){
    const card=node('div','voice-card');card.append(node('strong','',v.label),node('span','input-note',Math.round(v.seconds)+' s de parole détectée'));
    const listen=node('button','secondary','▶ Écouter un extrait');listen.onclick=()=>playExcerpt(v.sample_start,v.sample_end);
    const select=node('select','');select.setAttribute('aria-label','Prénom pour '+v.label);speakerOptions(select,m.participants||[],v.name);select.disabled=locked;
    select.onchange=()=>action(async()=>{await api('meetings/'+m.id+'/voices/'+v.id,'POST',{name:select.value});toast('Correspondance appliquée. Refaites le résumé pour l’actualiser.');});
    const reference=node('button','text-button','Utiliser cet extrait comme référence');reference.disabled=locked||v.sample_end-v.sample_start<3;reference.onclick=()=>prepareReference(v.sample_start,v.sample_end,v.name);
    card.append(listen,select,reference);list.append(card);
  }
}
function playExcerpt(start,end){
  const audio=$('audio');seek(start);audio.ontimeupdate=()=>{if(audio.currentTime>=end){audio.pause();audio.ontimeupdate=null;}};
}

function participantHint(prefix,saved=false){
  const names=[...new Set($(prefix+'-participants').value.split(/[,;\n]/).map(x=>x.trim()).filter(Boolean))];
  $(prefix+'-participants-note').textContent='Un prénom par ligne, ou séparés par des virgules. '+names.length+' participant'+(names.length>1?'s':'')+' saisi'+(names.length>1?'s':'')+(prefix==='meeting'?(saved?' — participants enregistrés.':' — cliquez sur « Enregistrer les participants ».'):'.');
}
for(const prefix of ['meeting','import','record'])$(prefix+'-participants').oninput=()=>participantHint(prefix);

function updateReferences(m, locked){
  const select=$('reference-name'),names=m.participants||[],key=JSON.stringify([m.id,names]);
  if(select.dataset.names!==key){select.dataset.names=key;const old=select.value;select.replaceChildren();speakerOptions(select,names,old);select.options[0].textContent='Choisir un participant';}
  const unavailable=locked||!m.segments.length||!state.voice_engine.installed;
  for(const id of ['reference-name','reference-start','reference-end','reference-play','reference-from-player'])$(id).disabled=unavailable;
  $('reference-save').disabled=unavailable||!names.length;
  const refs=m.voice_references||[],rkey=JSON.stringify([m.id,refs,locked,m.voice_reference_matches,names,m.segments.filter(s=>s.speaker_reference).length]);
  if(referencesKey===rkey)return;referencesKey=rkey;
  $('reference-status').textContent=!names.length?'Enregistrez d’abord les prénoms des participants.':refs.length?refs.length+' extrait'+(refs.length>1?'s':'')+' de référence · '+m.segments.filter(s=>s.speaker_reference).length+' passages attribués. Vérifiez les résultats dans la transcription.':'Vous pouvez aussi choisir « Utiliser ce passage comme référence » dans la transcription.';
  const list=$('reference-list');list.replaceChildren();
  refs.forEach((ref,index)=>{const row=node('div','reference-row');row.append(node('strong','',ref.name),node('span','',time(ref.start)+' → '+time(ref.end)));const listen=node('button','text-button','▶ Écouter');listen.onclick=()=>playExcerpt(ref.start,ref.end);const remove=node('button','text-button','Supprimer');remove.disabled=locked;remove.onclick=()=>action(()=>saveReferences(refs.filter((_,i)=>i!==index)));row.append(listen,remove);list.append(row);});
}
function prepareReference(start,end,name){
  $('participants-panel').open=true;$('reference-start').value=Math.round(start*10)/10;$('reference-end').value=Math.round(Math.min(end,start+20,current.duration)*10)/10;
  if(name)$('reference-name').value=name;
  $('reference-start').scrollIntoView({behavior:'smooth',block:'center'});playExcerpt(start,Math.min(end,start+20));
}
async function saveReferences(references){await api('meetings/'+selected+'/voice-references','POST',{references,execution:$('meeting-voice-execution').value});toast('Recherche des voix lancée. Les attributions seront appliquées à la fin.');}
$('reference-from-player').onclick=()=>{if(!current)return;const start=$('audio').currentTime||0;prepareReference(start,Math.min(current.duration,start+8));};
$('reference-play').onclick=()=>playExcerpt(Number($('reference-start').value),Number($('reference-end').value));
$('reference-save').onclick=()=>action(async()=>{const ref={name:$('reference-name').value,start:Number($('reference-start').value),end:Number($('reference-end').value)};if(!ref.name)throw new Error('Choisissez un participant enregistré.');if(ref.end-ref.start<3||ref.end-ref.start>20)throw new Error('Choisissez un extrait de 3 à 20 secondes.');const refs=current.voice_references||[];if(refs.some(r=>r.name===ref.name&&r.start===ref.start&&r.end===ref.end))throw new Error('Cet extrait est déjà enregistré pour ce participant.');await saveReferences([...refs,ref]);});
function renderTranscript(){
  if(!current)return;
  const list=$('transcript-list');list.replaceChildren();const query=$('transcript-search').value.toLocaleLowerCase('fr');
  const segments=current.segments.map((s,index)=>({s,index})).filter(({s})=>segmentDisplay(s).toLocaleLowerCase('fr').includes(query));
  if(!segments.length){empty(list,current.segments.length?'Aucun passage trouvé.':'La transcription apparaîtra ici.',current.segments.length?'Essayez un autre mot.':'Les premiers passages seront disponibles pendant le traitement.');return;}
  for(const {s,index} of segments){
    const row=node('div','transcript-row'),body=node('div','transcript-body');row.append(timeButton(s.start));
    const select=node('select','speaker-select');select.setAttribute('aria-label','Intervenant du passage à '+time(s.start));speakerOptions(select,current.participants||[],s.speaker);select.disabled=!!state.active||state.recording.active||!current.participants?.length;
    select.onchange=()=>action(async()=>{await api('meetings/'+current.id+'/speaker','POST',{index,start:s.start,speaker:select.value});toast('Passage attribué.');});
    body.append(select);
    if(s.voice||s.voice_uncertain)body.append(node('span','voice-hint',s.speaker_reference?'Correspondance avec un extrait · à vérifier':s.voice?'Voix '+s.voice.split('-')[1]+(s.speaker?' · attribution confirmée':' · prénom à confirmer'):'Voix ambiguë · à vérifier'));
    body.append(node('p','',s.text));
    if(s.end-s.start>=3){const reference=node('button','text-button transcript-reference','Utiliser ce passage comme référence');reference.disabled=!!state.active||state.recording.active;reference.onclick=()=>prepareReference(s.start,s.end,s.speaker);body.append(reference);}
    row.append(body);list.append(row);
  }
}

function setTab(value){tab=value;$('summary-content').hidden=value!=='summary';$('transcript-content').hidden=value!=='transcript';document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===value));}
function summaryText(r){return [r.title,'',...(r.participants?.length?['Participants déclarés : '+r.participants.join(', '),'']:[]),r.overview,'',...(r.topics||[]).flatMap(t=>[t.title,...t.points.map(p=>'• '+p),'']),'PROPOSITIONS À CONFIRMER',...(r.proposals||[]).map(d=>'• '+d.text),'','DÉCISIONS',...r.decisions.map(d=>'• '+d.text),'','ACTIONS',...r.actions.map(a=>'• '+a.task+' — '+a.owner+' — '+a.due),'','QUESTIONS OUVERTES',...r.questions.map(q=>'• '+q)].join('\n');}
$('nav-home').onclick=()=>view('home');document.querySelectorAll('[data-home]').forEach(b=>b.onclick=()=>view('home'));$('nav-models').onclick=()=>view('models');$('nav-record').onclick=showRecord;$('show-record').onclick=showRecord;
$('show-import').onclick=()=>{updateModels();$('import-dialog').showModal();$('import-path').focus();};$('close-import').onclick=()=>$('import-dialog').close();$('import-dialog').onclick=e=>{if(e.target===$('import-dialog')&&!$('import-submit').disabled){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close();}};
$('choose-file').onclick=()=>$('import-file').click();
$('import-file').onchange=()=>{const file=$('import-file').files[0];if(!file)return;importFile=file;$('import-path').value=file.name;$('import-path').setCustomValidity('');$('import-progress').hidden=true;};
$('import-path').oninput=()=>{importFile=null;$('import-file').value='';};
$('import-dialog').addEventListener('cancel',e=>{if($('import-submit').disabled)e.preventDefault();});
function uploadFile(file,metadata){return new Promise((resolve,reject)=>{const xhr=new XMLHttpRequest();const p=$('import-progress');p.hidden=false;p.textContent='Copie du fichier sur votre PC…';xhr.open('POST','/api/import-upload?'+new URLSearchParams({...metadata,filename:file.name}));xhr.setRequestHeader('X-Clair-Token',window.CLAIR_TOKEN);xhr.setRequestHeader('Content-Type','application/octet-stream');xhr.upload.onprogress=e=>{p.textContent=e.lengthComputable?'Copie locale du fichier : '+Math.round(e.loaded/e.total*100)+' %':'Copie du fichier sur votre PC…';};xhr.upload.onload=()=>{p.textContent='Fichier copié. Préparation de la transcription…';};xhr.onload=()=>{let value;try{value=JSON.parse(xhr.responseText);}catch{reject(new Error('Réponse inattendue du service local.'));return;}if(xhr.status>=200&&xhr.status<300)resolve(value);else reject(new Error(typeof value.detail==='string'?value.detail:'L’import du fichier n’a pas pu aboutir.'));};xhr.onerror=()=>reject(new Error('La copie a été interrompue. Vérifiez que Clair est ouvert et réessayez.'));xhr.onabort=()=>reject(new Error('Copie annulée.'));xhr.send(file);});}
$('import-form').onsubmit=e=>{e.preventDefault();action(async()=>{const b=$('import-submit'),original=b.textContent;const controls=[...$('import-form').querySelectorAll('input,select,textarea,button')];controls.forEach(c=>c.disabled=true);b.textContent='Import en cours…';try{const metadata={title:$('import-title').value,language:$('import-language').value,context:$('import-context').value,participants:$('import-participants').value,diarize:$('import-diarize').checked,speaker_count:Number($('import-speaker-count').value)||0,voice_execution:$('import-voice-execution').value,llm_model:$('import-model').value,execution:$('import-execution').value,auto_summary:$('import-mode').value==='summary'};const m=importFile?await uploadFile(importFile,metadata):await api('import','POST',{...metadata,path:$('import-path').value});$('import-dialog').close();importFile=null;$('import-file').value='';$('import-path').value='';await openMeeting(m.id);}finally{controls.forEach(c=>c.disabled=false);b.textContent=original;$('import-progress').hidden=true;}});};
$('start-record').onclick=()=>action(async()=>{await api('record/start','POST',{title:$('record-title').value,system_id:$('system-device').value?Number($('system-device').value):null,mic_id:$('mic-device').value?Number($('mic-device').value):null,language:$('record-language').value,context:$('record-context').value,participants:$('record-participants').value,diarize:$('record-diarize').checked,speaker_count:Number($('record-speaker-count').value)||0,voice_execution:$('record-voice-execution').value,llm_model:$('record-model').value,execution:$('record-execution').value});toast('Enregistrement démarré. Gardez Clair ouvert.');});
$('stop-record').onclick=()=>action(async()=>{const m=await api('record/stop','POST',{});await openMeeting(m.id);});
$('cancel-job').onclick=()=>action(()=>api('meetings/'+selected+'/cancel','POST',{}));$('generate-summary').onclick=()=>action(()=>api('meetings/'+selected+'/retry','POST',{summary_only:true,llm_model:$('summary-model').value,execution:$('summary-execution').value}));$('transcript-search').oninput=renderTranscript;
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>setTab(b.dataset.tab));
$('export-select').onchange=async e=>{const name=e.target.value;e.target.value='';if(!name||!selected)return;if(name.startsWith('compte-rendu')&&!current.report){toast('Le compte rendu n’est pas encore disponible.',true);return;}try{const res=await fetch('/api/meetings/'+selected+'/export/'+name);if(!res.ok)throw new Error('Cet export n’est pas encore disponible.');const url=URL.createObjectURL(await res.blob());const a=node('a','');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),10000);}catch(e){toast(e.message,true);}};
$('copy-content').onclick=async()=>{if(!current)return;const text=tab==='summary'?(current.report?summaryText(current.report):''):current.segments.map(s=>'['+time(s.start)+'] '+segmentDisplay(s)).join('\n');if(!text){toast('Le contenu n’est pas encore disponible.',true);return;}try{await navigator.clipboard.writeText(text);toast('Copié dans le presse-papiers.');}catch{toast('Le navigateur n’autorise pas la copie. Utilisez l’export.',true);}};
$('open-folder').onclick=()=>action(()=>api('folder','POST',{}));$('quit').onclick=()=>action(async()=>{await api('shutdown','POST',{});clearInterval(poll);toast('Clair est fermé. Vous pouvez fermer cet onglet.');});
const poll=setInterval(refresh,2000);refresh();
$('cancel-download').onclick=()=>action(()=>api('models/download/cancel','POST',{}));
$('default-execution').onchange=()=>action(()=>api('preferences','POST',{execution:$('default-execution').value}));

$('refresh-catalog').onclick=()=>action(()=>api('models/refresh','POST',{}));
$('auto-catalog').onchange=()=>action(()=>api('preferences','POST',{auto_catalog:$('auto-catalog').checked}));
$('model-search').oninput=updateModels;
$('install-voices').onclick=()=>action(()=>api('voices/install','POST',{}));
$('cancel-voice-install').onclick=()=>action(()=>api('voices/install/cancel','POST',{}));
$('save-participants').onclick=()=>action(async()=>{await api('meetings/'+selected+'/participants','POST',{participants:$('meeting-participants').value});lastContent='';toast('Participants enregistrés.');});
$('detect-voices').onclick=()=>action(()=>api('meetings/'+selected+'/diarize','POST',{speaker_count:Number($('meeting-speaker-count').value)||0,execution:$('meeting-voice-execution').value}));
let theme='system';try{theme=localStorage.getItem('clair-theme')||'system';}catch{}
if(!['system','light','dark'].includes(theme))theme='system';
const darkQuery=matchMedia('(prefers-color-scheme: dark)');
function applyTheme(){document.documentElement.dataset.theme=theme==='system'?(darkQuery.matches?'dark':'light'):theme;}
$('theme-select').value=theme;applyTheme();
$('theme-select').onchange=()=>{theme=$('theme-select').value;try{localStorage.setItem('clair-theme',theme);}catch{}applyTheme();};
darkQuery.addEventListener('change',()=>{if(theme==='system')applyTheme();});

$('retranscribe').onclick=()=>action(()=>api('meetings/'+selected+'/retry','POST',{summary_only:false,llm_model:$('summary-model').value,execution:$('summary-execution').value}));
