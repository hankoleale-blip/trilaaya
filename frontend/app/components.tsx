import Image from "next/image";
import Link from "next/link";
export function Brand({light=false}:{light?:boolean}) {
 return <Link href="/" className="flex items-center gap-3"><Image src="/trikaaya-logo.jpg" alt="Trikaaya logo" width={180} height={180} className="h-12 w-12 rounded-full object-cover"/><span className={`text-xl font-extrabold tracking-tight ${light?'text-white':'text-trikaaya-dark'}`}>trikaaya<span className="block text-[9px] font-extrabold tracking-[.3em] text-trikaaya-olive">TRI · FORM · BODY</span></span></Link>
}
export function Header(){return <header className="mx-auto flex max-w-7xl items-center justify-between px-5 py-5 md:px-8"><Brand/><nav className="hidden items-center gap-8 text-sm font-bold md:flex"><a href="/#about">About</a><a href="/#taekwondo">Taekwondo</a><a href="/#contact">Contact</a><Link href="/signin" className="rounded-full border border-trikaaya-dark/20 px-5 py-3">Sign in</Link></nav><Link href="/signin" className="rounded-full bg-trikaaya-dark px-5 py-3 text-sm font-bold text-white md:hidden">Sign in</Link></header>}
