package world.osaim.sms;

import android.app.job.JobInfo;
import android.app.job.JobParameters;
import android.app.job.JobScheduler;
import android.app.job.JobService;
import android.content.ComponentName;
import android.content.Context;
import android.content.SharedPreferences;
import android.database.Cursor;
import org.json.JSONObject;
import java.net.URL;
import javax.net.ssl.HttpsURLConnection;
import java.nio.charset.StandardCharsets;

public class UploadJob extends JobService {
    private volatile boolean stopped;
    private volatile HttpsURLConnection active;
    static void schedule(Context context) {
        JobInfo job=new JobInfo.Builder(17,new ComponentName(context,UploadJob.class))
            .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).setPersisted(true)
            .setBackoffCriteria(30000,JobInfo.BACKOFF_POLICY_EXPONENTIAL).build();
        context.getSystemService(JobScheduler.class).schedule(job);
    }
    public boolean onStartJob(JobParameters params) {
        stopped=false;
        new Thread(()->{
            boolean retry=false;
            SharedPreferences prefs=getSharedPreferences("sender",0);
            try(Queue queue=new Queue(this)) {
                // Delete unsent SMS older than seven days, too.
                queue.getWritableDatabase().delete("outbox","received<?",new String[]{String.valueOf(System.currentTimeMillis()/1000-7*86400)});
                try(Cursor rows=queue.getReadableDatabase().rawQuery("SELECT id,sender,body,received FROM outbox ORDER BY received",null)) {
                    while(!stopped && prefs.getBoolean("enabled",false) && rows.moveToNext()) {
                        JSONObject payload=new JSONObject();
                        payload.put("event",rows.getString(0)); payload.put("sender",rows.getString(1));
                        payload.put("body",rows.getString(2)); payload.put("received",rows.getLong(3));
                        active=(HttpsURLConnection)new URL(prefs.getString("url","")+"/api/messages").openConnection();
                        active.setInstanceFollowRedirects(false); active.setConnectTimeout(15000); active.setReadTimeout(15000);
                        active.setRequestMethod("POST"); active.setDoOutput(true);
                        active.setRequestProperty("Content-Type","application/json");
                        active.setRequestProperty("Authorization","Bearer "+prefs.getString("token",""));
                        byte[] bytes=payload.toString().getBytes(StandardCharsets.UTF_8);
                        active.setFixedLengthStreamingMode(bytes.length);
                        try(java.io.OutputStream out=active.getOutputStream()) { out.write(bytes); }
                        int result=active.getResponseCode(); active.disconnect(); active=null;
                        if(result==401) { prefs.edit().putBoolean("enabled",false).putString("status","Device key rejected. Reconnect this phone.").apply(); break; }
                        if(result!=200) { retry=true; break; }
                        queue.getWritableDatabase().delete("outbox","id=?",new String[]{rows.getString(0)});
                        prefs.edit().putString("status","Last upload: "+new java.util.Date()).apply();
                    }
                }
            } catch(Exception error) {
                retry=true;
                prefs.edit().putString("status","Upload pending. Check connection and server address.").apply();
            } finally {
                if(active!=null) active.disconnect(); active=null;
                if(!stopped) jobFinished(params,retry);
            }
        },"sms-upload").start();
        return true;
    }
    public boolean onStopJob(JobParameters params) {
        stopped=true;
        if(active!=null) active.disconnect();
        return getSharedPreferences("sender",0).getBoolean("enabled",false);
    }
}
