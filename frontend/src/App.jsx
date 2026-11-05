import { BrowserRouter, Routes, Route } from "react-router-dom";

import MainLayout from "./layouts/MainLayout";
import CheckIn from "./pages/CheckIn";
import Users from "./pages/Users";
import Sections from "./pages/Sections";
import Subjects from "./pages/Subjects";
import Reports from "./pages/Reports";
import Semesters from "./pages/Semesters";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<MainLayout />}>
          <Route
            path="/"
            element={<CheckIn />}
          />

          <Route
            path="/users"
            element={<Users />}
          />

          <Route
            path="/sections"
            element={<Sections />}
          />

          <Route
            path="/subjects"
            element={<Subjects />}
          />

          <Route
            path="/reports"
            element={<Reports />}
          />
        
          <Route
            path="/semesters"
            element={<Semesters />}
          />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;