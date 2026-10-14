package world.osaim.sms;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
public class BootReceiver extends BroadcastReceiver {
    public void onReceive(Context context,Intent intent) {
        if(Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction()) && context.getSharedPreferences("sender",0).getBoolean("enabled",false)) UploadJob.schedule(context);
    }
}
