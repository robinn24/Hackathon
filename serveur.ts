import cors from "cors";
app.use(cors({
  origin: ["http://localhost:3000", "http://192.168.1.20:3000"],
  credentials: true
}));
