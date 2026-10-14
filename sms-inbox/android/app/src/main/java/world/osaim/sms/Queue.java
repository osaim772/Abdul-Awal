package world.osaim.sms;

import android.content.Context;
import android.content.ContentValues;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;

class Queue extends SQLiteOpenHelper {
    Queue(Context context) { super(context,"outbox.db",null,1); }
    public void onCreate(SQLiteDatabase db) { db.execSQL("CREATE TABLE outbox(id TEXT PRIMARY KEY,sender TEXT,body TEXT,received INTEGER)"); }
    public void onUpgrade(SQLiteDatabase db,int oldVersion,int newVersion) { }
    void add(String sender,String body,long received) {
        ContentValues values=new ContentValues();
        values.put("id",java.util.UUID.randomUUID().toString()); values.put("sender",sender);
        values.put("body",body); values.put("received",received);
        getWritableDatabase().insertOrThrow("outbox",null,values);
    }
}
