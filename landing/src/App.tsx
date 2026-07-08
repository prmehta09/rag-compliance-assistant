import { Navbar } from "./components/Navbar";
import { Hero } from "./components/Hero";
import { Results } from "./components/Results";
import { SpotlightScene } from "./components/SpotlightScene";

function App() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-void">
      <SpotlightScene />
      <Navbar />
      <Hero />
      <Results />
    </main>
  );
}

export default App;
