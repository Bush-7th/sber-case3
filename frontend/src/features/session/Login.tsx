import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  ClipboardCheck,
  ScanText,
  ShieldCheck,
} from "lucide-react";
import { api, setSession } from "../../shared/api/client";
import { useCommand } from "../../shared/api/queries";
import { ErrorNotice } from "../../shared/ui";

export function Login() {
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const client = useQueryClient();
  const navigate = useNavigate();
  const mutation = useCommand(
    () => api.login(login.trim(), password),
    (session) => {
      setSession(session);
      client.setQueryData(["session"], session);
      setPassword("");
      navigate("/packages");
    },
  );
  return (
    <div className="login-layout">
      <section className="login-story">
        <div className="brand">
          <ClipboardCheck />
          Агентство инноваций
        </div>
        <div className="story-body">
          <span className="eyebrow">ПРОВЕРКА ДОКУМЕНТОВ</span>
          <h1>
            Больше внимания
            <br />
            решению.
            <br />
            <span>Меньше — рутине.</span>
          </h1>
          <p>
            Состав пакета, найденные данные и результаты проверки — в одном
            рабочем месте.
          </p>
          <div className="story-feature">
            <ScanText />
            <span>
              От исходного документа
              <br />к объяснимому результату
            </span>
          </div>
        </div>
        <small>
          Система помогает проверить документы. Решение остаётся за вами.
        </small>
      </section>
      <section className="login-form-wrap">
        <form
          className="login-form"
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
        >
          <span className="eyebrow">РАБОЧЕЕ МЕСТО</span>
          <h2>Вход в систему</h2>
          <p>Используйте учётную запись специалиста или администратора.</p>
          <label>
            Логин
            <input
              name="username"
              autoComplete="username"
              autoFocus
              required
              value={login}
              onChange={(e) => setLogin(e.target.value)}
              disabled={mutation.isPending}
            />
          </label>
          <label>
            Пароль
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={mutation.isPending}
            />
          </label>
          <ErrorNotice error={mutation.error} />
          <button
            className="button primary full"
            disabled={mutation.isPending || !login.trim()}
          >
            {mutation.isPending ? "Входим…" : "Войти"}
            <ArrowRight size={18} />
          </button>
          <div className="login-security">
            <ShieldCheck size={16} />
            Документы доступны только после входа
          </div>
        </form>
      </section>
    </div>
  );
}
