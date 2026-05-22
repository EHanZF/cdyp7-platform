import express from "express";
import axios from "axios";
import cors from "cors";

const app = express();
app.use(cors());

const PORT = process.env.PORT || 7071;

// ✅ cache layer
let cache = null;
let lastFetch = 0;
const TTL = 60000; // 60 seconds

app.get("/api/dashboard", async (req, res) => {
  const now = Date.now();

  // ✅ Serve cached data
  if (cache && now - lastFetch < TTL) {
    return res.json(cache);
  }

  try {
    const query = "status != 'Closed'";

    const response = await axios.get(
      `${process.env.CB_URL}/rest/query`,
      {
        headers: {
          Authorization: `Bearer ${process.env.CB_TOKEN}`,
        },
        params: {
          query,
          // ✅ optimize payload
          fields: "id,name,status,priority,assignedTo",
          pageSize: 1000
        },
      }
    );

    const items = response.data.items || [];

    // ✅ reduce payload further
    const optimized = items.map(i => ({
      id: i.id,
      name: i.name,
      status: i.status,
      priority: i.priority,
      assignee: i.assignedTo?.name || null
    }));

    cache = optimized;
    lastFetch = now;

    res.json(optimized);

  } catch (err) {
    console.error(err.message);
    res.status(500).json({ error: "Failed to fetch Codebeamer data" });
  }
});

app.listen(PORT, () => {
  console.log(`API running on port ${PORT}`);
});