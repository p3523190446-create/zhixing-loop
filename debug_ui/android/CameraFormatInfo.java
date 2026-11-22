package cn.zhixing.dashboard;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

/** Optional native format metadata must not prevent an advertised MJPEG stream. */
final class CameraFormatInfo {
  static final class Raw {
    boolean seen;
    boolean supported=true;
    final List<String> names=new ArrayList<>();
    boolean usable(){return seen&&supported;}
  }
  static Raw inspect(String nativeFormats)throws JSONException {
    JSONArray formats=new JSONObject(nativeFormats).getJSONArray("formats");
    Raw result=new Raw();
    for(int index=0;index<formats.length();index++){
      JSONObject format=formats.getJSONObject(index);
      if(format.optInt("subType")!=4)continue; // UVC VS_FORMAT_UNCOMPRESSED.
      result.seen=true;
      JSONObject detail=format.optJSONObject("detail");
      String guid=(detail==null?format.optString("GUID",""):detail.optString("GUID","")).toLowerCase(Locale.US);
      if(guid.startsWith("59555932"))result.names.add("YUY2");
      else if(guid.startsWith("55595659"))result.names.add("UYVY");
      else result.supported=false;
    }
    return result;
  }
}
