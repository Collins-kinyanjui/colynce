(()=>{const toggle=document.querySelector('.menu-toggle'),nav=document.querySelector('.nav-items');if(toggle&&nav){toggle.addEventListener('click',()=>{const open=nav.classList.toggle('open');toggle.setAttribute('aria-expanded',String(open));toggle.textContent=open?'Close ✕':'Menu ☰'});nav.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>{nav.classList.remove('open');toggle.setAttribute('aria-expanded','false')}))}const observer=typeof IntersectionObserver!=='undefined'?new IntersectionObserver(items=>{items.forEach(x=>{if(x.isIntersecting){x.target.classList.add('visible');observer.unobserve(x.target)}})},{threshold:.1}):null;document.querySelectorAll('.reveal').forEach(el=>observer?observer.observe(el):el.classList.add('visible'));const form=document.getElementById('visionForm');if(form){const interest=new URLSearchParams(location.search).get('service');const select=document.getElementById('interest');if(interest&&[...select.options].some(o=>o.value===interest))select.value=interest;form.addEventListener('submit',async event=>{event.preventDefault();const button=form.querySelector('button[type=submit]');const status=document.getElementById('formStatus');button.disabled=true;status.textContent='Sending your request…';try{const payload=Object.fromEntries(new FormData(form));const res=await fetch('/api/leads',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});let data=await res.json();if(!res.ok)throw Error(typeof data.detail==='string'?data.detail:'Please check your details and try again.');form.reset();status.textContent='Thank you — we received your request. Reference: '+data.reference+'. We will review your vision and get in touch.'}catch(err){status.textContent=err.message||'Unable to submit right now. Please retry.'}finally{button.disabled=false}})}})();

/* Conversational lead capture. The assistant asks one question at a time; no form UI. */
(()=>{
 const launch=document.createElement('button');launch.type='button';launch.className='assistant-launch';
 launch.setAttribute('aria-label','Open COKIT Digital AI assistant');launch.setAttribute('aria-expanded','false');
 launch.textContent='✦ AI Assistant';
 const pane=document.createElement('section');pane.className='assistant-pane';pane.hidden=true;
 pane.setAttribute('role','dialog');pane.setAttribute('aria-label','COKIT Digital AI assistant');
 const head=document.createElement('div');head.className='assistant-head';
 const heading=document.createElement('div');const title=document.createElement('strong');title.textContent='✦ COKIT AI Assistant';
 const subtitle=document.createElement('small');subtitle.textContent='Talk to us about your next project';
 heading.append(title,subtitle);
 const close=document.createElement('button');close.type='button';close.className='assistant-close';
 close.setAttribute('aria-label','Close assistant');close.textContent='×';head.append(heading,close);
 const messages=document.createElement('div');messages.className='assistant-messages';
 messages.setAttribute('role','log');messages.setAttribute('aria-live','polite');
 const bottom=document.createElement('div');bottom.className='assistant-bottom';
 const form=document.createElement('form');form.className='assistant-form';
 const input=document.createElement('input');input.className='assistant-input';input.type='text';
 input.maxLength=2000;input.required=true;input.autocomplete='off';
 input.placeholder='Type your message…';input.setAttribute('aria-label','Your message');
 const send=document.createElement('button');send.type='submit';send.className='assistant-send';send.textContent='Send';
 const info=document.createElement('p');info.className='assistant-disclaimer';
 info.textContent='To submit a project request, tell me “I want to submit an interest.” Never share passwords or payment details.';
 form.append(input,send);bottom.append(form,info);pane.append(head,messages,bottom);document.body.append(launch,pane);
 const history=[];let busy=false;let intake=null;
 const stages=['name','business','email','interest','message','confirm'];
 const questions={
  name:'Of course! I can submit your project interest to our team. What is your full name?',
  business:'Thank you. What is your business or organization name?',
  email:'What email address should our team use to contact you?',
  interest:'What would you like us to build? For example, a dashboard, website, automation, AI assistant or integration.',
  message:'Please describe your vision. What should it do, and what goals do you want to achieve?',
  confirm:'I have all your details. May I send your request to the COKIT Digital dashboard now? Reply YES to submit or NO to cancel.'
 };
 const labels={name:'Name',business:'Business',email:'Email',interest:'Project',message:'Vision'};
 function bubble(message,who){const node=document.createElement('div');node.className='assistant-bubble '+who;node.textContent=message;messages.append(node);messages.scrollTop=messages.scrollHeight;return node}
 function say(message){bubble(message,'bot')}
 say('Welcome to COKIT Digital! I can help with websites, automation, AI assistants and integrations. You can also tell me you want to submit an interest, and I will collect the details right here.');
 function setOpen(open){pane.hidden=!open;launch.setAttribute('aria-expanded',String(open));launch.setAttribute('aria-label',open?'Close COKIT Digital AI assistant':'Open COKIT Digital AI assistant');if(open)input.focus();else launch.focus()}
 launch.addEventListener('click',()=>setOpen(pane.hidden));close.addEventListener('click',()=>setOpen(false));
 document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!pane.hidden)setOpen(false)});
 function wantsIntake(message){return /\b(submit|send|register|start|make|create|leave|give)\b.{0,65}\b(interest|inquiry|enquiry|request|vision|project|quote|consultation)\b/i.test(message)||/\b(interested in submitting|want to be contacted|can you take my details|can i submit)\b/i.test(message)}
 function emailValid(value){return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)&&value.length<=254}
 function validate(stage,value){
  if(stage==='email')return emailValid(value)?'':'That email address does not look valid. Please enter an address such as name@example.com.';
  if(stage==='name'&&(value.length<2||value.length>100))return 'Please provide your full name (2–100 characters).';
  if(stage==='business'&&(value.length<2||value.length>120))return 'Please provide the business or organization name (2–120 characters).';
  if(stage==='interest'&&(value.length<2||value.length>120))return 'Please describe what you would like built in a few words (2–120 characters).';
  if(stage==='message'&&(value.length<5||value.length>2000))return 'Please describe your vision using 5–2,000 characters.';
  return '';
 }
 function startIntake(){intake={index:0,details:{}};say(questions.name);input.placeholder='Your full name…'}
 function stopIntake(){intake=null;input.placeholder='Type your message…'}
 function promptNext(){const stage=stages[intake.index];input.placeholder=stage==='confirm'?'YES or NO…':stage==='message'?'Describe your vision…':'Type your answer…';if(stage==='confirm'){const d=intake.details;say('Here is your request summary:\n'+Object.keys(labels).map(key=>labels[key]+': '+d[key]).join('\n')+'\n\n'+questions.confirm)}else say(questions[stage])}
 async function submitIntake(){
  busy=true;send.disabled=true;input.disabled=true;say('Submitting your request to the team dashboard…');
  try{const response=await fetch('/api/leads',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(intake.details)});
   const result=await response.json();
   if(!response.ok)throw Error(typeof result.detail==='string'?result.detail:'The server did not accept your request.');
   say('Your interest has been submitted successfully! Reference: '+result.reference+'. The request is now in our team dashboard. Thank you for choosing COKIT Digital.');
   stopIntake();
  }catch(error){say('I could not submit your interest: '+(error.message||'Please try again.')+' Reply YES to retry or NO to cancel. Your request has not been confirmed.')}
  finally{busy=false;send.disabled=false;input.disabled=false;input.focus()}
 }
 async function processIntake(message){
  const value=message.trim();const stage=stages[intake.index];
  if(/^(cancel|stop|never mind|nevermind)$/i.test(value)){say('I have cancelled the request. Nothing was submitted. We can continue chatting.');stopIntake();return}
  if(stage==='confirm'){
   if(/^(yes|y|confirm|submit|send it|go ahead|okay|ok)$/i.test(value)){await submitIntake();return}
   if(/^(no|n|cancel|stop)$/i.test(value)){say('No problem. Your request was not submitted.');stopIntake();return}
   if(/^(edit|change|restart|start over)$/i.test(value)){say('Certainly. We can start again.');startIntake();return}
   say('Please reply YES to submit, NO to cancel, or EDIT to start again.');return;
  }
  const error=validate(stage,value);if(error){say(error);return}
  intake.details[stage]=value;intake.index+=1;promptNext();
 }
 form.addEventListener('submit',async event=>{
  event.preventDefault();if(busy)return;const question=input.value.trim();if(!question)return;
  input.value='';bubble(question,'user');
  if(intake){await processIntake(question);return}
  if(wantsIntake(question)){startIntake();return}
  busy=true;send.disabled=true;input.disabled=true;const thinking=bubble('Thinking…','bot');
  try{const response=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:question,history:history.slice(-8)})});
   const data=await response.json();if(!response.ok)throw Error('Chat is temporarily unavailable.');
   const answer=typeof data.reply==='string'&&data.reply.trim()?data.reply:'Tell me more about your project.';
   thinking.textContent=answer;history.push({role:'user',content:question},{role:'assistant',content:answer});
   if(history.length>8)history.splice(0,history.length-8);
   if(/\b(where|how)\b.*\b(submit|request|interest)\b/i.test(question))say('If you prefer, just say “I want to submit an interest” and I will ask for each detail here.');
  }catch(error){thinking.textContent='I could not respond right now. Please try again, or say “submit an interest” to send a request.'}
  finally{busy=false;send.disabled=false;input.disabled=false;input.focus()}
 });
})();
