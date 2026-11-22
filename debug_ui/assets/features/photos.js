import {$,text} from '../core/dom.js';

export function createPhotos(api){
  let ready=false,busy=false;
  const link=$('photoDownload');
  function buttons(){$('takePhoto').disabled=!ready||busy;}
  function saved(photo){
    link.href=api.base+'/api/photo/'+encodeURIComponent(photo.id)+'/download';
    link.download=photo.id+'.jpg';link.hidden=false;
    text('photoMessage','照片已存入采集端；点“下载照片”可保存在当前设备。');
  }
  async function capture(){
    if(!ready||busy)return;busy=true;buttons();text('photoMessage','正在保存当前新鲜画面…');
    try{saved(await api.post('photo/capture',{},7000));}
    catch(error){text('photoMessage','拍照未完成：'+error.message);}
    finally{busy=false;buttons();}
  }
  $('takePhoto').addEventListener('click',capture);
  api.get('photo/list').then(list=>{if(Array.isArray(list)&&list.length)saved(list[0]);}).catch(()=>{});
  buttons();return {setReady(value){ready=Boolean(value);buttons();}};
}
