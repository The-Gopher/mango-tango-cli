
import type { ActionFunctionArgs, MetaFunction } from "@remix-run/node";
import { Form, useLoaderData } from "@remix-run/react";
import ProjectType from "~/types/project";
import { redirect } from "@remix-run/node";



export const loader = async (x: any) => {
    console.log(x);
    const data = await fetch("http://localhost:5000/api/projects").then((res) => res.json());
    // Return the data to expose through useLoaderData()
    return data;
};

export async function action({
    request,
}: ActionFunctionArgs) {
    console.log(request);
    return null
}



export default function Index() {




    return <div>
        <Form method="post">
            <input name="name" type="text" />

            <button type="submit">Submit</button>
        </Form>
    </div>
}