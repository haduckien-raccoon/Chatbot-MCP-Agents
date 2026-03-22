# SGroup Multi-Agent Chatbot

Chatbot multi-agent cho SGroup su dung:
- Gemini (`google-genai`)
- LangGraph de dieu phoi graph agent
- FastAPI async cho backend
- HTML/CSS/JS thuan cho frontend
- OpenWeather, NewsAPI (co RSS fallback), Exa, Brave Search
- MCP server (stdio) de tich hop voi MCP client

## 1. Cau truc du an

```
sgroup-chatbot/
├── main.py
├── requirements.txt
├── .env
├── .env.example
├── .gitignore
├── README.md
├── graph/
├── agents/
├── modules/
├── services/
├── api/
├── config/
└── static/
```

## 2. Cai dat

### Buoc 1: Tao virtual environment

```bash
python -m venv venv
source venv/bin/activate
# Windows: venv\Scripts\activate
```

### Buoc 2: Cai dependencies

```bash
pip install -r requirements.txt
```

### Buoc 3: Cau hinh bien moi truong

```bash
cp .env.example .env
```

Can dien cac key:
- `GOOGLE_API_KEY`
- `OPENWEATHER_API_KEY`
- `EXA_API_KEY` (tuy chon)
- `NEWS_API_KEY` (tuy chon)
- `BRAVE_API_KEY` (tuy chon)
- `DATA_DIR` (mac dinh `../data`)

### Du lieu SGroup dat o dau?

Dat bo du lieu tai thu muc duoc tro boi `DATA_DIR`.

Voi cau hinh mac dinh:
- Project: `sgroup-chatbot/`
- Data: `../data/`

Can co cac file:
- `sgroup.json`
- `ai-team.json`
- `sgroup-site.json`
- Thu muc `docs/` cho technical docs (neu co)

He thong hien da data-driven cho cac nhom:
- `sgroup_knowledge` doc tu `sgroup.json` + `sgroup-site.json`
- `ai_team` doc tu `ai-team.json`
- `module_a` va `module_b` map theo module trong `ai-team.json`

## 3. Chay du an

```bash
python main.py
```

Mo trinh duyet tai:
- http://localhost:8000

## 4. Chay MCP server (buoc 2 ban yeu cau)

### 4.1 Start MCP server

```bash
python mcp_server.py
```

Server MCP chay qua `stdio` va expose cac tools:
- `chat(message, session_id="default")`
- `weather(location)`
- `news(query)`
- `clear_chat(session_id)`
- `health()`

### 4.2 Cau hinh MCP client ket noi

Su dung file mau:
- `docs/mcp-client-config.example.json`

Copy vao cau hinh MCP client cua ban va thay:
- duong dan Python venv
- duong dan cwd den thu muc du an

Transport dang dung la `stdio`:
1. MCP client spawn process `python mcp_server.py`
2. Client va server trao doi JSON-RPC qua stdin/stdout
3. Client goi `list_tools` -> nhan danh sach tool
4. Client goi `call_tool` de chay `chat`/`weather`/`news`

## 5. API endpoints

- `POST /api/chat`
  - body:
    ```json
    {
      "message": "thoi tiet tai Ha Noi hom nay",
      "session_id": "default"
    }
    ```
- `DELETE /api/chat/{session_id}`
- `GET /api/health`

## 6. Luong xu ly

1. User gui tin nhan qua UI.
2. `POST /api/chat` tao `AgentState`.
3. LangGraph chay 3 node:
   - `orchestrate_node` -> chon agent
   - `fetch_external_data_node` -> lay du lieu API neu can
   - `generate_response_node` -> sinh cau tra loi
4. Luu history theo `session_id`.
5. Tra ve `reply`, `agent_used`, `session_id`.

## 7. Ghi chu

- Neu khong co `NEWS_API_KEY`, he thong tu fallback sang RSS feed.
- Neu khong co `EXA_API_KEY`, IT agent fallback sang Brave (neu co key).
- Session memory la in-memory dict, phu hop cho local/dev.
- De tang do chinh xac thong tin SGroup, cap nhat truc tiep bo du lieu trong `DATA_DIR` thay vi sua prompt hard-code.
