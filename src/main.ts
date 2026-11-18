import {surface,panel,label,rect,mint,amber,report,type Frame} from "@shared/surface";
import {loadValues} from "@shared/settings";

type Snapshot={session:string;word:string;count:number;state:string};
let config="",snap:Snapshot|null=null,shown=0,goal=10,connected=false,closed=false,reading=false,page=0,stage=-1;
let nextPoll:ReturnType<typeof setTimeout>|undefined, animation:ReturnType<typeof setTimeout>|undefined;
const sparks=[[0,-1],[1,-1],[1,0],[1,1],[0,1],[-1,1],[-1,0],[-1,-1]];
const uk:Record<string,string>={а:"a",б:"b",в:"v",г:"h",ґ:"g",д:"d",е:"e",є:"ye",ж:"zh",з:"z",и:"y",і:"i",ї:"yi",й:"y",к:"k",л:"l",м:"m",н:"n",о:"o",п:"p",р:"r",с:"s",т:"t",у:"u",ф:"f",х:"kh",ц:"ts",ч:"ch",ш:"sh",щ:"shch",ь:"",ю:"yu",я:"ya"};
function displayWord(text:string){return text.toLowerCase().split("").map(c=>uk[c]??c).join("").replace(/[^\x20-\x7E]/g,"")||"word";}
function draw():Frame{
 const total=snap?.count||0;
 const word=displayWord(snap?.word||"listen");
 const frames:Frame=[label("word",word.toUpperCase(),1,0,amber,"front","tiny"),
 label("total",String(shown),1,5,mint,"front","bold"),...panel("WORD BURST",[
 connected?snap?.state||"Connected":config?"Bridge offline":"Set bridge URL",page?"Target: "+goal:"Word: "+word,
 "Heard "+total+" / goal "+goal,page?"Click: adjust goal":"Click: refresh",
 "Wheel: count or target","Start: restart goal from here"])];
 const radius=[1,3,5,7,8][stage];
 if(radius!==undefined){
   sparks.forEach(([dx,dy],i)=>frames.push(rect("s"+i,54+dx*radius,Math.max(0,Math.min(15,7+dy*radius)),stage<2?2:1,1,stage<3?amber:mint)));
 }else{
   const fill=Math.min(18,Math.round(shown/Math.max(1,goal)*18));
   for(let i=0;i<6;i++)frames.push(rect("m"+i,45+i*4,12-i,2,2+i,i*3<fill?mint:"#33433FFF"));
 }
 return frames;
}
function tick(){
 animation=undefined;
 if(closed||!snap)return;
 if(stage<0&&shown<snap.count){shown++;stage=0;}
 else if(stage>=0){stage++;if(stage>4)stage=-1;}
 refresh();
 if(stage>=0||shown<snap.count)animation=setTimeout(tick,75);else animation=undefined;
}
async function poll(){
 if(reading||closed||!config)return;reading=true;
 if(nextPoll!==undefined)clearTimeout(nextPoll);nextPoll=undefined;
 try{
   const response=await fetch(config);if(!response.ok)throw Error("HTTP "+response.status);
   const data=await response.json() as Snapshot;
   if(!Number.isInteger(data.count)||data.count<0||typeof data.word!=="string"||typeof data.session!=="string")throw Error("Bad count");
   if(snap?.session!==data.session||data.count<shown){if(animation!==undefined)clearTimeout(animation);animation=undefined;stage=-1;shown=data.count;}
   snap=data;connected=true;
   if(animation===undefined&&shown<data.count)tick();
 }catch(e){connected=false;console.log("word bridge",String(e));}
 finally{reading=false;if(!closed){refresh();nextPoll=setTimeout(()=>{nextPoll=undefined;void poll();},connected?1750:7000);}}
}
const refresh=surface(draw,k=>{
 if(k==="up"||k==="down")page=1-page;
 else if(k==="ok"&&page)goal=goal>=50?5:goal+5;
 else if(k==="ok")void poll();
 else if(k==="start")goal=shown+5;
},()=>{closed=true;if(nextPoll!==undefined)clearTimeout(nextPoll);if(animation!==undefined)clearTimeout(animation);},{enabled:false});
void loadValues().then(v=>{if(closed)return;config=String(v?.bridge||"").trim();refresh();if(config)void poll();}).catch(report);
