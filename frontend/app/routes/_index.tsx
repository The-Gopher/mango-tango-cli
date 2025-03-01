import type { MetaFunction } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import ProjectType from "~/types/project";



export const meta: MetaFunction = () => {
  return [
    { title: "New Remix App" },
    { name: "description", content: "Welcome to Remix!" },
  ];
};

export const loader = async () => {
  const data = await fetch("http://localhost:5000/api/projects").then((res) => res.json());
  // Return the data to expose through useLoaderData()
  return data;
};

export default function Index() {

  const data = useLoaderData<ProjectType[]>();

  console.log(data);

  return (
    <div>
      {data.map((item) => (
        <div key={item.directory_name}>{item.name}</div>
      ))}
      TODO
    </div>
  );
}


