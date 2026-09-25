package com.aegis.mobile.ui

import android.graphics.Color
import android.os.Bundle
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.Spinner
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import android.view.ViewGroup
import android.view.LayoutInflater
import android.view.View
import com.aegis.mobile.R
import com.aegis.mobile.data.PrefKeys
import com.aegis.mobile.data.dataStore
import com.aegis.mobile.network.RetrofitClient
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

class CommunityActivity : AppCompatActivity() {
    private data class Room(val id: String, val title: String)
    private data class Msg(val name: String, val body: String, val at: String)

    private val rooms = mutableListOf<Room>()
    private val messages = mutableListOf<Msg>()
    private lateinit var adapter: MsgAdapter
    private lateinit var spinner: Spinner
    private lateinit var input: EditText

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_community)
        spinner = findViewById(R.id.roomSpinner)
        input = findViewById(R.id.msgInput)
        val list = findViewById<RecyclerView>(R.id.msgList)
        adapter = MsgAdapter(messages)
        list.layoutManager = LinearLayoutManager(this)
        list.adapter = adapter
        findViewById<Button>(R.id.sendBtn).setOnClickListener { send() }
        spinner.setOnItemSelectedListener(object : android.widget.AdapterView.OnItemSelectedListener {
            override fun onItemSelected(p: android.widget.AdapterView<*>?, v: View?, pos: Int, id: Long) {
                loadMessages()
            }
            override fun onNothingSelected(p: android.widget.AdapterView<*>?) {}
        })
        loadRooms()
    }

    private fun loadRooms() {
        lifecycleScope.launch {
            try {
                val api = RetrofitClient.getApiService(this@CommunityActivity)
                val resp = api.communityRooms()
                if (!resp.isSuccessful) {
                    Toast.makeText(this@CommunityActivity, "Rooms HTTP ${resp.code()}", Toast.LENGTH_SHORT).show()
                    return@launch
                }
                @Suppress("UNCHECKED_CAST")
                val rows = (resp.body()?.get("rooms") as? List<Map<String, Any?>>) ?: emptyList()
                rooms.clear()
                rows.forEach {
                    val id = (it["id"] ?: it["slug"] ?: "").toString()
                    val title = (it["title"] ?: id).toString()
                    if (id.isNotBlank()) rooms.add(Room(id, title))
                }
                runOnUiThread {
                    spinner.adapter = ArrayAdapter(
                        this@CommunityActivity,
                        android.R.layout.simple_spinner_dropdown_item,
                        rooms.map { it.title }
                    )
                    loadMessages()
                }
            } catch (e: Exception) {
                Toast.makeText(this@CommunityActivity, e.message ?: "error", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun loadMessages() {
        val pos = spinner.selectedItemPosition
        if (pos < 0 || pos >= rooms.size) return
        val roomId = rooms[pos].id
        lifecycleScope.launch {
            try {
                val api = RetrofitClient.getApiService(this@CommunityActivity)
                val resp = api.communityMessages(roomId, 50)
                if (!resp.isSuccessful) return@launch
                @Suppress("UNCHECKED_CAST")
                val rows = (resp.body()?.get("messages") as? List<Map<String, Any?>>) ?: emptyList()
                messages.clear()
                rows.forEach {
                    messages.add(
                        Msg(
                            (it["display_name"] ?: "?").toString(),
                            (it["body"] ?: "").toString(),
                            (it["created_at"] ?: "").toString().take(19)
                        )
                    )
                }
                runOnUiThread { adapter.notifyDataSetChanged() }
            } catch (_: Exception) {}
        }
    }

    private fun send() {
        val text = input.text?.toString()?.trim().orEmpty()
        if (text.isEmpty()) return
        val pos = spinner.selectedItemPosition
        if (pos < 0 || pos >= rooms.size) return
        val roomId = rooms[pos].id
        lifecycleScope.launch {
            try {
                val prefs = dataStore.data.first()
                val accountId = prefs[PrefKeys.ACCOUNT_ID]?.trim().orEmpty()
                if (accountId.isEmpty()) {
                    Toast.makeText(this@CommunityActivity, "Set Account ID in Settings", Toast.LENGTH_SHORT).show()
                    return@launch
                }
                val api = RetrofitClient.getApiService(this@CommunityActivity)
                val resp = api.communityPost(roomId, mapOf("account_id" to accountId, "body" to text))
                if (!resp.isSuccessful) {
                    Toast.makeText(this@CommunityActivity, "Send HTTP ${resp.code()}", Toast.LENGTH_SHORT).show()
                    return@launch
                }
                runOnUiThread {
                    input.setText("")
                    loadMessages()
                }
            } catch (e: Exception) {
                Toast.makeText(this@CommunityActivity, e.message ?: "error", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private class MsgAdapter(private val items: List<Msg>) :
        RecyclerView.Adapter<MsgAdapter.VH>() {
        class VH(val tv: TextView) : RecyclerView.ViewHolder(tv)
        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
            val tv = TextView(parent.context)
            tv.setTextColor(Color.parseColor("#E8F0FF"))
            tv.textSize = 13f
            tv.setPadding(8, 8, 8, 8)
            return VH(tv)
        }
        override fun getItemCount() = items.size
        override fun onBindViewHolder(holder: VH, position: Int) {
            val m = items[position]
            holder.tv.text = "${m.name} · ${m.at}\n${m.body}"
        }
    }
}
