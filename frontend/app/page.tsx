import { FeatureCards } from "@/components/home/FeatureCards";
import { HeroSection } from "@/components/home/HeroSection";
import { HowItWorks } from "@/components/home/HowItWorks";
import { SafetyNotice } from "@/components/home/SafetyNotice";
import { StartChatCTA } from "@/components/home/StartChatCTA";
import { Footer } from "@/components/layout/Footer";
import { Header } from "@/components/layout/Header";
import { UQBrandBar } from "@/components/layout/UQBrandBar";

export default function Home() {
  return (
    <>
      <UQBrandBar />
      <Header activePage="home" />
      <main>
        <HeroSection />
        <FeatureCards />
        <HowItWorks />
        <SafetyNotice />
        <StartChatCTA />
      </main>
      <Footer />
    </>
  );
}
