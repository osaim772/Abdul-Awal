package world.osaim.sms;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.provider.Telephony;
import android.telephony.SmsMessage;

public class SmsReceiver extends BroadcastReceiver {
    public void onReceive(Context context,Intent intent) {
        if(!Telephony.Sms.Intents.SMS_RECEIVED_ACTION.equals(intent.getAction())) return;
        if(!context.getSharedPreferences("sender",0).getBoolean("enabled",false)) return;
        SmsMessage[] parts=Telephony.Sms.Intents.getMessagesFromIntent(intent);
        if(parts==null||parts.length==0) return;
        StringBuilder body=new StringBuilder();
        for(SmsMessage part:parts) body.append(part.getMessageBody());
        try(Queue queue=new Queue(context)) {
            queue.add(parts[0].getOriginatingAddress()==null?"Unknown":parts[0].getOriginatingAddress(),body.toString(),parts[0].getTimestampMillis()/1000);
        }
        UploadJob.schedule(context);
    }
}
