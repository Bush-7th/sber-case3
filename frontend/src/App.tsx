import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  NavLink,
  Navigate,
  Route,
  Routes,
  useNavigate,
} from "react-router-dom";
import {
  ClipboardCheck,
  Files,
  LogOut,
  Settings2,
  ShieldCheck,
} from "lucide-react";
import { api } from "./shared/api/client";
import { endSession, resolveSession, useCommand } from "./shared/api/queries";
import { ErrorNotice, Loading } from "./shared/ui";
import { Login } from "./features/session/Login";
import { PackageList } from "./features/packages/PackageList";
import { PackageWorkspace } from "./features/packages/PackageWorkspace";
import { AdminWorkspace } from "./features/admin/AdminWorkspace";

export function App() {
  const session = useQuery({
    queryKey: ["session"],
    queryFn: ({ signal }) => resolveSession(signal),
    // Recover the cookie-backed session and CSRF after a reload.
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
  const client = useQueryClient();
  const navigate = useNavigate();
  const logout = useCommand(
    () => api.logout(),
    () => {
      endSession(client);
      navigate("/login");
    },
  );
  if (session.isPending) return <Loading />;
  if (session.error)
    return (
      <div className="connection-page">
        <div className="brand">
          <ClipboardCheck />
          Агентство инноваций
        </div>
        <h1>Подключение к рабочему месту</h1>
        <ErrorNotice
          error={session.error}
          retry={() => void session.refetch()}
        />
        <p>Для входа нужен запущенный сервер приложения.</p>
      </div>
    );
  if (!session.data)
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  const { user } = session.data;
  const home = user.role === "admin" ? "/admin" : "/packages";
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Перейти к содержимому
      </a>
      <aside className="sidebar">
        <NavLink className="brand" to={home}>
          <span className="brand-mark">
            <ClipboardCheck size={22} />
          </span>
          <span>
            Агентство <br />
            инноваций
          </span>
        </NavLink>
        <div className="nav-caption">РАБОЧЕЕ МЕСТО</div>
        <nav aria-label="Основная навигация">
          {user.role === "specialist" && (
            <NavLink to="/packages">
              <Files size={18} />
              Заявки
            </NavLink>
          )}
          {user.role === "admin" && (
            <NavLink to="/admin">
              <Settings2 size={18} />
              Программы и правила
            </NavLink>
          )}
        </nav>
        <div className="sidebar-note">
          <ShieldCheck size={20} />
          <p>
            Предварительная проверка
            <span>Окончательное решение принимает специалист.</span>
          </p>
        </div>
        <div className="user-card">
          <span className="avatar">{user.name.slice(0, 1).toUpperCase()}</span>
          <div>
            <strong>{user.name}</strong>
            <small>
              {user.role === "admin" ? "Администратор" : "Специалист"}
            </small>
          </div>
          <button
            className="icon-button"
            aria-label="Выйти"
            onClick={() => logout.mutate()}
            disabled={logout.isPending}
          >
            <LogOut size={17} />
          </button>
        </div>
      </aside>
      <div className="main-wrap">
        <header className="topbar">
          <span>Проверка документов на субсидию</span>
          <span className="topbar-label">
            <span className="status-dot" />
            Защищённое рабочее место
          </span>
        </header>
        <main id="main">
          <ErrorNotice error={logout.error} />
          <Routes>
            <Route
              path="/packages"
              element={user.role === "specialist" ? <PackageList /> : <Navigate to="/admin" replace />}
            />
            <Route
              path="/packages/:id"
              element={user.role === "specialist" ? <PackageWorkspace /> : <Navigate to="/admin" replace />}
            />
            <Route
              path="/admin/*"
              element={
                user.role === "admin" ? (
                  <AdminWorkspace />
                ) : (
                  <Navigate to="/packages" replace />
                )
              }
            />
            <Route path="*" element={<Navigate to={home} replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
