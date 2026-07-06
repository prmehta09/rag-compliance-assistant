import { Navbar } from "./components/Navbar";
import { Hero } from "./components/Hero";
import { SpotlightScene } from "./components/SpotlightScene";

function App() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-void">
      <SpotlightScene />
      <Navbar />
      <Hero />
    </main>
  );
}

export default App;
