import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Home from './pages/Home';
import Discussion from './pages/Discussion';
import DiscussionRoom from './pages/DiscussionRoom';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/discussion/:id" element={<Discussion />} />
        <Route path="/room/:id" element={<DiscussionRoom />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;