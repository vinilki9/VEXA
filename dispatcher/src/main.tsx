import React from 'react';
import { createRoot } from 'react-dom/client';
import { LayoutDashboard, Map, CarFront, Users, Wallet, Settings, Bell, Search, Activity } from 'lucide-react';
import './style.css';

const orders = [
  ['VX-1048','Аэропорт → Центр','Economy','Поиск водителя','teal'],
  ['VX-1047','ул. Ленина, 12 → Вокзал','Comfort','В пути','blue'],
  ['VX-1046','Центр → Бизнес-парк','Business','Ожидает подачи','amber'],
  ['VX-1045','Северный район → Центр','Comfort+','Завершён','gray']
];
function App(){
 return <div className="shell">
  <aside><div className="brand"><span className="mark">V</span><b>VEXA</b><small>DISPATCH</small></div>
   <nav><a className="active"><LayoutDashboard/>Обзор</a><a><Map/>Карта</a><a><CarFront/>Заказы</a><a><Users/>Водители</a><a><Wallet/>Финансы</a><a><Settings/>Настройки</a></nav>
   <div className="branch"><span className="dot"/>Москва · Главный филиал</div>
  </aside>
  <main><header><div><p className="eyebrow">ПАНЕЛЬ УПРАВЛЕНИЯ</p><h1>Обзор диспетчера</h1></div><div className="headright"><span className="online"><i/>Система активна</span><Bell/><div className="avatar">АД</div></div></header>
   <section className="stats">
    <article><label>Заказы сегодня</label><strong>248</strong><small className="positive">+12,8% к вчера</small></article>
    <article><label>Водители на линии</label><strong>86</strong><small>из 112 активных</small></article>
    <article><label>Среднее ожидание</label><strong>4,2 <em>мин</em></strong><small className="positive">−0,6 мин</small></article>
    <article><label>Оборот сегодня</label><strong>186 420 <em>₽</em></strong><small>демонстрационные данные</small></article>
   </section>
   <section className="content">
    <article className="mapcard"><div className="cardhead"><div><h2>Карта города</h2><p>Положение автомобилей и активные заказы</p></div><span className="live"><i/> LIVE DEMO</span></div>
     <div className="maparea"><div className="road r1"/><div className="road r2"/><div className="road r3"/><div className="river"/><span className="district d1">ЦЕНТР</span><span className="district d2">СЕВЕР</span><span className="district d3">ВОСТОК</span>{Array.from({length:13},(_,i)=><span key={i} className="car" style={{left:`${12+(i*23)%78}%`,top:`${18+(i*31)%68}%`}}>⌖</span>)}<div className="maplegend"><span><i className="tealbg"/>На линии</span><span><i className="bluebg"/>Заказ</span></div></div>
    </article>
    <article className="orders"><div className="cardhead"><div><h2>Последние заказы</h2><p>Список демонстрационных заказов</p></div><button>Все заказы</button></div>
     {orders.map(o=><div className="order" key={o[0]}><div className="ordericon"><CarFront/></div><div className="orderinfo"><b>{o[0]}</b><span>{o[1]}</span><small>{o[2]}</small></div><span className={`status ${o[4]}`}>{o[3]}</span></div>)}
    </article>
   </section>
   <section className="bottom"><div><Activity/><b>Операционная активность</b><span>Показатели интерфейса — демонстрационные, API не подключён.</span></div><div className="barset">{[34,52,45,72,60,88,66,94,75,83,58,97].map((h,i)=><i key={i} style={{height:h+'%'}}/>)}</div></section>
  </main>
 </div>
}
createRoot(document.getElementById('root')!).render(<App/>);
