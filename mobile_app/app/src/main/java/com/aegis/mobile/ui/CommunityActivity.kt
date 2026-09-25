package com.aegis.mobile.ui

import android.graphics.Color
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.Spinner
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.aegis.mobile.R
import com.aegis.mobile.data.PrefKeys
import com.aegis.mobile.data.dataStore
import com.aegis.mobile.network.RetrofitClient
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

class CommunityActivity : AppCompatActivity() {
    private data class Room(val id: String, val title: String)
    private data class Msg(val id: Int, val name: String, val body: String, val at: String)

    private val rooms = mutableListOf<Room>()
    private val messages = mutableListOf<Msg>()
    private lateinit var adapter: MsgAdapter
    private lateinit var spinner: Spinner
    private lateinit var input: EditText
    private lateinit var onlineBadge: TextView
    private lateinit var onlineList: TextView
    private lateinit var myNameLabel: TextView
    private var accountId: String = ""
    private var lastMsgId: Int = 0
    private val handler = Handler(Looper.getMainLooper())
    private val pollRunnable = object : Runnable {
        override fun run() {
            heartbeatAndPoll()
            handler.postDelayed(this, 5_000L)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_community)
        spinner = findViewById(R.id.roomSpinner)
        input = findViewById(R.id.msgInput)
        onlineBadge = findViewById(R.id.onlineBadge)
        onlineList = findViewById(R.id.onlineList)
        myNameLabel = findViewById(R.id.myNameLabel)
        val list = findViewById<RecyclerView>(R.id.msgList)
        adapter = MsgAdapter(messages)
        list.layoutManager = LinearLayoutManager(this)
        list.adapter = adapter
        findViewById<Button>(R.id.sendBtn).setOnClickListener { send() }
        findViewById<TextView>(R.id.editNameBtn).setOnClickListener { promptDisplayName(force = true) }
        findViewById<TextView>(R.id.editNameBtn).setOnLongClickListener {
            openDmDialog(); true
        }
        onlineBadge.setOnClickListener { openDmDialog() }
        spinner.setOnItemSelectedListener(object : android.widget.AdapterView.OnItemSelectedListener {
            override fun onItemSelected(p: android.widget.AdapterView<*>?, v: View?, pos: Int, id: Long) {
                lastMsgId = 0
                messages.clear()
                adapter.notifyDataSetChanged()
                loadMessages(full = true)
            }
            override fun onNothingSelected(p: android.widget.AdapterView<*>?) {}
        })
        lifecycleScope.launch {
            accountId = dataStore.data.first()[PrefKeys.ACCOUNT_ID]?.trim().orEmpty()
            if (accountId.isEmpty()) {
                Toast.makeText(this@CommunityActivity, "Set Account ID in Settings", Toast.LENGTH_LONG).show()
            }
            loadRooms()
            ensureProfile()
        }
    }

    override fun onResume() {
        super.onResume()
        handler.removeCallbacks(pollRunnable)
        handler.post(pollRunnable)
    }

    override fun onPause() {
        handler.removeCallbacks(pollRunnable)
        super.onPause()
    }

    private fun ensureProfile() {
        lifecycleScope.launch {
            try {
                val api = RetrofitClient.getApiService(this@CommunityActivity)
                val resp = api.communityProfile(accountId)
                if (resp.isSuccessful) {
                    val set = resp.body()?.get("display_name_set") == true
                    val name = (resp.body()?.get("display_name") ?: "").toString()
                    runOnUiThread {
                        myNameLabel.text = "You: $name"
                        if (!set) promptDisplayName(force = false)
                    }
                }
            } catch (_: Exception) {}
        }
    }

    private fun promptDisplayName(force: Boolean) {
        val box = EditText(this)
        box.hint = "e.g. ApexTrader"
        box.setTextColor(Color.WHITE)
        box.setHintTextColor(Color.GRAY)
        box.setBackgroundColor(Color.parseColor("#132238"))
        box.setPadding(24, 24, 24, 24)
        AlertDialog.Builder(this)
            .setTitle(if (force) "Change display name" else "Choose your chat name")
            .setMessage("3–24 characters. Letters, numbers, underscore. Shown to other traders.")
            .setView(box)
            .setPositiveButton("Save") { _, _ ->
                val name = box.text?.toString()?.trim().orEmpty()
                if (name.isEmpty()) return@setPositiveButton
                lifecycleScope.launch {
                    try {
                        val api = RetrofitClient.getApiService(this@CommunityActivity)
                        val resp = api.communitySetProfile(
                            mapOf("account_id" to accountId, "display_name" to name)
                        )
                        if (!resp.isSuccessful) {
                            Toast.makeText(
                                this@CommunityActivity,
                                "Name rejected (${resp.code()}). Try another.",
                                Toast.LENGTH_LONG
                            ).show()
                            return@launch
                        }
                        val saved = (resp.body()?.get("display_name") ?: name).toString()
                        runOnUiThread { myNameLabel.text = "You: $saved" }
                    } catch (e: Exception) {
                        Toast.makeText(this@CommunityActivity, e.message ?: "error", Toast.LENGTH_SHORT).show()
                    }
                }
            }
            .setNegativeButton(if (force) "Cancel" else "Later", null)
            .show()
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
                applyOnline(resp.body())
                runOnUiThread {
                    spinner.adapter = ArrayAdapter(
                        this@CommunityActivity,
                        android.R.layout.simple_spinner_dropdown_item,
                        rooms.map { it.title }
                    )
                    loadMessages(full = true)
                }
            } catch (e: Exception) {
                Toast.makeText(this@CommunityActivity, e.message ?: "error", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun applyOnline(body: Map<String, Any?>?) {
        if (body == null) return
        val count = (body["online_count"] as? Number)?.toInt() ?: 0
        @Suppress("UNCHECKED_CAST")
        val online = (body["online"] as? List<Map<String, Any?>>) ?: emptyList()
        val names = online.mapNotNull { it["display_name"]?.toString() }.take(12)
        runOnUiThread {
            onlineBadge.text = "● $count online"
            onlineList.text = if (names.isEmpty()) "Online: —" else "Online: ${names.joinToString(", ")}"
        }
    }

    private fun heartbeatAndPoll() {
        if (accountId.isEmpty()) return
        lifecycleScope.launch {
            try {
                val api = RetrofitClient.getApiService(this@CommunityActivity)
                val pres = api.communityPresence(mapOf("account_id" to accountId))
                if (pres.isSuccessful) {
                    applyOnline(pres.body())
                    val name = (pres.body()?.get("profile") as? Map<*, *>)?.get("display_name")
                    if (name != null) {
                        runOnUiThread { myNameLabel.text = "You: $name" }
                    }
                }
                loadMessages(full = false)
            } catch (_: Exception) {}
        }
    }

    private fun loadMessages(full: Boolean) {
        val pos = spinner.selectedItemPosition
        if (pos < 0 || pos >= rooms.size) return
        val roomId = rooms[pos].id
        lifecycleScope.launch {
            try {
                val api = RetrofitClient.getApiService(this@CommunityActivity)
                val after = if (full || lastMsgId <= 0) null else lastMsgId
                val resp = api.communityMessages(roomId, 50, after)
                if (!resp.isSuccessful) return@launch
                @Suppress("UNCHECKED_CAST")
                val rows = (resp.body()?.get("messages") as? List<Map<String, Any?>>) ?: emptyList()
                if (full) {
                    messages.clear()
                    lastMsgId = 0
                }
                rows.forEach {
                    val id = (it["id"] as? Number)?.toInt() ?: 0
                    if (id > 0 && messages.none { m -> m.id == id }) {
                        messages.add(
                            Msg(
                                id,
                                (it["display_name"] ?: "?").toString(),
                                (it["body"] ?: "").toString(),
                                (it["created_at"] ?: "").toString().take(19).replace('T', ' ')
                            )
                        )
                        if (id > lastMsgId) lastMsgId = id
                    }
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
                if (accountId.isEmpty()) {
                    Toast.makeText(this@CommunityActivity, "Set Account ID in Settings", Toast.LENGTH_SHORT).show()
                    return@launch
                }
                val api = RetrofitClient.getApiService(this@CommunityActivity)
                val resp = api.communityPost(roomId, mapOf("account_id" to accountId, "body" to text))
                if (!resp.isSuccessful) {
                    Toast.makeText(this@CommunityActivity, "Send failed (${resp.code()})", Toast.LENGTH_SHORT).show()
                    return@launch
                }
                runOnUiThread {
                    input.setText("")
                    loadMessages(full = false)
                }
            } catch (e: Exception) {
                Toast.makeText(this@CommunityActivity, e.message ?: "error", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private inner class MsgAdapter(private val items: List<Msg>) :
        RecyclerView.Adapter<MsgAdapter.VH>() {
        class VH(val tv: TextView) : RecyclerView.ViewHolder(tv)
        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
            val tv = TextView(parent.context)
            tv.setTextColor(Color.parseColor("#E8F0FF"))
            tv.textSize = 13f
            tv.setPadding(8, 10, 8, 10)
            return VH(tv)
        }
        override fun getItemCount() = items.size
        override fun onBindViewHolder(holder: VH, position: Int) {
            val m = items[position]
            val att = if (m.body.startsWith("[image]")) " 📎" else ""
            holder.tv.text = "${m.name}  ·  ${m.at}$att\n${m.body}"
            holder.tv.setOnLongClickListener {
                reportMessage(m.id, m.name)
                true
            }
        }
    }

    private fun reportMessage(messageId: Int, who: String) {
        val box = EditText(this)
        box.hint = "Why are you reporting this?"
        box.setTextColor(Color.WHITE)
        box.setPadding(24, 24, 24, 24)
        AlertDialog.Builder(this)
            .setTitle("Report message from $who")
            .setView(box)
            .setPositiveButton("Report") { _, _ ->
                val reason = box.text?.toString()?.trim().orEmpty()
                if (reason.length < 3) return@setPositiveButton
                lifecycleScope.launch {
                    try {
                        val api = RetrofitClient.getApiService(this@CommunityActivity)
                        val pos = spinner.selectedItemPosition
                        val roomId = if (pos in rooms.indices) rooms[pos].id else null
                        val resp = api.communityReport(
                            mapOf(
                                "account_id" to accountId,
                                "target_type" to "room",
                                "target_message_id" to messageId,
                                "reason" to reason,
                                "room_id" to (roomId ?: "")
                            )
                        )
                        Toast.makeText(
                            this@CommunityActivity,
                            if (resp.isSuccessful) "Report submitted" else "Report failed",
                            Toast.LENGTH_SHORT
                        ).show()
                    } catch (_: Exception) {}
                }
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun openDmDialog() {
        val box = EditText(this)
        box.hint = "Peer display name"
        box.setTextColor(Color.WHITE)
        box.setPadding(24, 24, 24, 24)
        AlertDialog.Builder(this)
            .setTitle("Direct message")
            .setMessage("Enter the exact display name of the trader (from Online list).")
            .setView(box)
            .setPositiveButton("Open") { _, _ ->
                val peer = box.text?.toString()?.trim().orEmpty()
                if (peer.isEmpty()) return@setPositiveButton
                lifecycleScope.launch {
                    try {
                        val api = RetrofitClient.getApiService(this@CommunityActivity)
                        val resp = api.communityDmOpen(
                            mapOf("account_id" to accountId, "peer_display_name" to peer)
                        )
                        if (!resp.isSuccessful) {
                            Toast.makeText(this@CommunityActivity, "DM open failed", Toast.LENGTH_SHORT).show()
                            return@launch
                        }
                        val threadId = (resp.body()?.get("thread_id") ?: "").toString()
                        val peerName = (resp.body()?.get("peer_display_name") ?: peer).toString()
                        runOnUiThread { openDmThread(threadId, peerName) }
                    } catch (e: Exception) {
                        Toast.makeText(this@CommunityActivity, e.message ?: "error", Toast.LENGTH_SHORT).show()
                    }
                }
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun openDmThread(threadId: String, peerName: String) {
        val log = TextView(this)
        log.setTextColor(Color.WHITE)
        log.textSize = 13f
        log.setPadding(16, 16, 16, 16)
        val input = EditText(this)
        input.hint = "Message to $peerName"
        input.setTextColor(Color.WHITE)
        input.setPadding(16, 16, 16, 16)
        val wrap = android.widget.LinearLayout(this)
        wrap.orientation = android.widget.LinearLayout.VERTICAL
        wrap.addView(log)
        wrap.addView(input)
        fun refreshDm() {
            lifecycleScope.launch {
                try {
                    val api = RetrofitClient.getApiService(this@CommunityActivity)
                    val resp = api.communityDmMessages(threadId, accountId, 50, null)
                    if (!resp.isSuccessful) return@launch
                    @Suppress("UNCHECKED_CAST")
                    val rows = (resp.body()?.get("messages") as? List<Map<String, Any?>>) ?: emptyList()
                    val sb = StringBuilder()
                    rows.forEach {
                        sb.append("${it["display_name"]}: ${it["body"]}\n")
                    }
                    runOnUiThread { log.text = sb.toString() }
                } catch (_: Exception) {}
            }
        }
        refreshDm()
        AlertDialog.Builder(this)
            .setTitle("DM · $peerName")
            .setView(wrap)
            .setPositiveButton("Send") { d, _ ->
                val text = input.text?.toString()?.trim().orEmpty()
                if (text.isEmpty()) return@setPositiveButton
                lifecycleScope.launch {
                    try {
                        val api = RetrofitClient.getApiService(this@CommunityActivity)
                        api.communityDmPost(
                            threadId,
                            mapOf("account_id" to accountId, "body" to text)
                        )
                        refreshDm()
                    } catch (_: Exception) {}
                }
            }
            .setNegativeButton("Close", null)
            .show()
    }
}
