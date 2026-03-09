import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';
import LoginPage from './pages/LoginPage';
import HomePage from './pages/HomePage';
import PromptsPage from './pages/PromptsPage';
import PromptFormPage from './pages/PromptFormPage';
import PromptViewPage from './pages/PromptViewPage';
import TasksPage from './pages/TasksPage';
import TaskFormPage from './pages/TaskFormPage';
import TaskDetailPage from './pages/TaskDetailPage';
import ResultsPage from './pages/ResultsPage';
import UsersPage from './pages/UsersPage';
import SettingsPage from './pages/SettingsPage';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />

          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route path="/" element={<HomePage />} />
            <Route path="/prompts" element={<PromptsPage />} />
            <Route path="/prompts/new" element={<PromptFormPage />} />
            <Route path="/prompts/:id/view" element={<PromptViewPage />} />
            <Route path="/prompts/:id/edit" element={<PromptFormPage />} />
            <Route path="/tasks" element={<TasksPage />} />
            <Route path="/tasks/new" element={<TaskFormPage />} />
            <Route path="/tasks/:id" element={<TaskDetailPage />} />
            <Route path="/tasks/:id/edit" element={<TaskFormPage />} />
            <Route path="/tasks/:id/results" element={<ResultsPage />} />
            <Route path="/users" element={<UsersPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
