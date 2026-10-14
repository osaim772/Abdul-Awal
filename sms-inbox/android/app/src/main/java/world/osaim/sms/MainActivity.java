package world.osaim.sms;

import android.Manifest;
import android.app.Activity;
import android.app.job.JobScheduler;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.text.InputType;
import android.widget.*;
import java.net.URI;

public class MainActivity extends Activity {
    EditText address,key; TextView status; SharedPreferences prefs;
    public void onCreate(Bundle state) {
        super.onCreate(state); prefs=getSharedPreferences("sender",0);
        LinearLayout layout=new LinearLayout(this); layout.setOrientation(LinearLayout.VERTICAL); layout.setPadding(32,48,32,24);
        ImageView logo=new ImageView(this); logo.setImageResource(world.osaim.sms.R.drawable.app_logo); logo.setContentDescription("OsAim Dev.World"); logo.setAdjustViewBounds(true); layout.addView(logo,new LinearLayout.LayoutParams(240,240));
        TextView title=new TextView(this); title.setText("Personal SMS Sender"); title.setTextSize(26); layout.addView(title);
        TextView explanation=new TextView(this); explanation.setText("Only connect a phone you own. When enabled, NEW incoming SMS, including OTPs, are uploaded to your private inbox. This phone must stay online. Android may delay uploads. This does not read old SMS.\n\nUse the HTTPS inbox address and device key created inside your inbox."); layout.addView(explanation);
        address=new EditText(this); address.setHint("https://your-private-inbox.example"); address.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI); address.setText(prefs.getString("url","")); layout.addView(address);
        key=new EditText(this); key.setHint("Device key"); key.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD); key.setText(prefs.getString("token","")); layout.addView(key);
        CheckBox consent=new CheckBox(this); consent.setText("I own this phone and consent to forwarding its new SMS and OTPs."); layout.addView(consent);
        Button enable=new Button(this); enable.setText("Enable SMS forwarding"); layout.addView(enable);
        status=new TextView(this); layout.addView(status);
        enable.setOnClickListener(v->{
            if(!consent.isChecked()) { status.setText("Confirm ownership and consent first."); return; }
            String url=address.getText().toString().trim();
            try { URI uri=new URI(url); if(!"https".equals(uri.getScheme())||uri.getHost()==null||uri.getRawUserInfo()!=null||uri.getRawQuery()!=null||uri.getRawFragment()!=null||!(uri.getPath().isEmpty()||uri.getPath().equals("/"))) throw new Exception(); }
            catch(Exception error) { status.setText("Use an HTTPS origin with no path, query or credentials."); return; }
            if(key.getText().toString().trim().length()<32) { status.setText("Paste the device key from your private inbox."); return; }
            prefs.edit().putString("url",url.replaceAll("/+$","")).putString("token",key.getText().toString().trim()).apply();
            if(checkSelfPermission(Manifest.permission.RECEIVE_SMS)!=PackageManager.PERMISSION_GRANTED) requestPermissions(new String[]{Manifest.permission.RECEIVE_SMS},1);
            else activate();
        });
        Button stop=new Button(this); stop.setText("Stop forwarding and delete unsent SMS"); layout.addView(stop);
        stop.setOnClickListener(v->{prefs.edit().putBoolean("enabled",false).remove("token").putString("status","Forwarding stopped.").apply(); getSystemService(JobScheduler.class).cancel(17);try(Queue q=new Queue(this)){q.getWritableDatabase().delete("outbox",null,null);}key.setText("");update();});
        Button refresh=new Button(this); refresh.setText("Refresh status / retry pending uploads"); layout.addView(refresh);
        refresh.setOnClickListener(v->{if(prefs.getBoolean("enabled",false)) UploadJob.schedule(this);update();});
        ScrollView scroll=new ScrollView(this); scroll.addView(layout);setContentView(scroll);update();
    }
    private void activate(){prefs.edit().putBoolean("enabled",true).putString("status","Waiting for a new SMS. Send a test message to this phone.").apply();UploadJob.schedule(this);update();}
    private void update(){status.setText((prefs.getBoolean("enabled",false)?"Forwarding enabled\n":"Forwarding disabled\n")+prefs.getString("status","Not connected."));}
    public void onRequestPermissionsResult(int request,String[] permissions,int[] results){super.onRequestPermissionsResult(request,permissions,results);if(request==1&&results.length>0&&results[0]==PackageManager.PERMISSION_GRANTED)activate();else status.setText("SMS permission is required. Forwarding is disabled.");}
}
