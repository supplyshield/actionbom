import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import Layout from "./components/Layout";
import RepositoriesPage from "./pages/RepositoriesPage";
import WorkflowsPage from "./pages/WorkflowsPage";
import WorkflowDetailPage from "./pages/WorkflowDetailPage";
import ActionsInventoryPage from "./pages/ActionsInventoryPage";
import ActionDetailPage from "./pages/ActionDetailPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<RepositoriesPage />} />
            <Route path="/repo/:repoId" element={<WorkflowsPage />} />
            <Route path="/workflow/:workflowId" element={<WorkflowDetailPage />} />
            <Route path="/actions" element={<ActionsInventoryPage />} />
            <Route path="/actions/*" element={<ActionDetailPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
      <Toaster theme="system" richColors position="bottom-right" />
    </QueryClientProvider>
  );
}
