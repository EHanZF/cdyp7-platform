import { useEffect, useState } from "react";

function App() {
  const [data, setData] = useState([]);

  const API_URL = import.meta.env.DEV
    ? "http://localhost:7071/api/dashboard"
    : "https://your-api.azurewebsites.net/api/dashboard";

  useEffect(() => {
  const fetchData = () => {
    fetch(API_URL)
      .then(res => res.json())
      .then(setData);
  };

  fetchData(); // initial load

  const interval = setInterval(fetchData, 30000);

  return () => clearInterval(interval);
}, []);
  return (
    <div>
      <h1>Codebeamer Dashboard</h1>

      <table border="1">
        <thead>
          <tr>
            IDNameStatusPriorityAssignee
          </tr>
        </thead>
        <tbody>
          {data.map(item => (
            <tr key={item.id}>
              <td>{item.id}</td>
              <td>{item.name}</td>
              <td>{item.status}</td>
              <td>{item.priority}</td>
              <td>{item.assignee}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default App;